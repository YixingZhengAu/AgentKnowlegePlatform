"""M3 相似问题生成:给每条候选 QA 补 3–5 条改写问法(扩召回面)。

实测结论见 documents/S1-PLAN.md §5 M3(160 → 144 句,平均 4.0 条/QA)。
集成只换一处:openai 直调 → Provider 层 **light tier**;prompt 与过滤逻辑一字不改。

为什么独立于 M2:抽取管"从原文挖出什么"(要保真、要带出处),相似问管"同一问题有几种问法"
(要发散、要口语化),目标不同、模型档位不同、prompt 分开调分开评。

★ 本层的两道代码硬约束(模型只负责产出,能不能留由代码判):
  ① 与标准问归一化后相同的改写直接丢(实测每轮稳定 16 条,留着白占一行向量);
  ② **跨条冲突检测**:一句改写与别的候选的问题面高度相似就丢 ——
    同一句问法映射到两个不同答案,检索必然选错一个,是精准问答最致命的脏数据。

⚠ prompt 里 rule 1b(不许把问题问宽)是被 M4 评测倒逼加出来的:
v1 给"用了哪些训练技巧"生成了 `How is YOLOv3 trained?`,直接导致"训练要多久"
这类**原文没答案**的问题以 0.70+ 命中它。加反例后消失。删这条规则等于把那个 bug 请回来。
"""

import asyncio
import time
from collections import Counter

from app.core.logging import get_logger
from app.providers import LLMResult
from app.schemas.exact_qa import QaCandidate, QaCandidateSet, SimilarQuestions
from app.services.exact_qa.llm import parse_structured
from app.services.exact_qa.matching import conflicting_face, normalize

log = get_logger(__name__)

#: 每条 QA 生成几条改写(SimilarQuestions 上限 8)
DEFAULT_N = 4
#: 并发条数。light 模型单条约 3–8s,8 路并发时 36 条实测约 50s
DEFAULT_CONCURRENCY = 8
MAX_TOKENS = 1024

SYSTEM_PROMPT = """\
You expand the retrieval surface of a verified-answer knowledge base.

Given one question and its verified answer, write {n} alternative ways a real employee might ask \
for that same answer. These rephrasings are embedded alongside the original question, so a user \
who phrases things differently still hits the verified answer.

Rules:
1. Same information need, different wording. Every rephrasing must be answered *completely* by \
the given answer — no broader, no narrower, no extra conditions.
1b. Never widen a question by dropping what it is about. If the question asks which training \
techniques are used, "How is YOLOv3 trained?" is WRONG: it invites answers about datasets, \
schedules and duration that the given answer does not contain. A rephrasing that a curious user \
would expect *more* from than the answer provides is a bad rephrasing — it will hijack unrelated \
questions and return this answer to them. Keep every qualifier of the original question.
2. Vary the surface form, not the meaning: synonyms, word order, question vs. imperative \
("How many layers does Darknet-53 have?" / "Darknet-53 layer count?" / "Tell me the number of \
layers in Darknet-53."). Include at least one short keyword-style phrasing and at least one \
full natural sentence.
3. Stay self-contained. Keep the entity and metric names explicit — never "it", "that model", \
"the table". A rephrasing that drops the subject would match the wrong knowledge entry.
4. Keep the distinguishing details. If the question is about ResNet-101, every rephrasing must \
still say ResNet-101; never generalise it to "ResNet" or "the backbone".
5. Do not restate the answer, do not add facts, do not ask anything the answer does not cover.
6. English only. No numbering, no quotes around the questions.
"""


async def gen_one(cand: QaCandidate, n: int) -> tuple[list[str], LLMResult]:
    """对单条 QA 调 light 模型产出改写。"""
    parsed, result = await parse_structured(
        SimilarQuestions,
        instructions=SYSTEM_PROMPT.format(n=n),
        user_input=f"Question: {cand.standard_question}\nAnswer: {cand.answer}",
        tier="light",
        max_tokens=MAX_TOKENS,
    )
    return list(parsed.questions), result


# ---------------------------------------------------- 过滤(纯函数,可离线测)


def filter_similar(
    candidates: list[QaCandidate], raw_lists: list[list[str]]
) -> Counter[str]:
    """把各条的原始改写过滤后**就地写回** `candidate.similar_questions`,返回统计。

    过滤必须串行:要看全局问题面(某条的改写不能撞上别条的标准问或已接受的改写)。
    """
    # 全局问题面:先放各条标准问(它们本身就是索引面,改写不能与之撞车)
    faces: list[tuple[int, str]] = [(i, c.standard_question) for i, c in enumerate(candidates)]
    stats: Counter[str] = Counter()

    for i, (cand, raw) in enumerate(zip(candidates, raw_lists, strict=True)):
        stats["raw"] += len(raw)
        kept: list[str] = []
        seen_norm = {normalize(cand.standard_question)}
        for q in (x.strip() for x in raw):
            if not q:
                continue
            if normalize(q) in seen_norm:
                stats["drop_same_as_standard"] += 1
                continue
            other = conflicting_face(q, i, faces)
            if other is not None:
                stats["drop_conflict"] += 1
                log.info(
                    "exact_qa_similar_conflict",
                    question=q,
                    conflicts_with=candidates[other].standard_question,
                )
                continue
            seen_norm.add(normalize(q))
            kept.append(q)
            faces.append((i, q))  # 已接受的改写也进问题面,防后面的条目撞它
        stats["kept"] += len(kept)
        cand.similar_questions = kept
        if not kept:
            stats["items_empty"] += 1
    return stats


# ------------------------------------------------------------------- 生成主体


async def fill_similar(
    cs: QaCandidateSet,
    *,
    n: int = DEFAULT_N,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[Counter[str], list[LLMResult]]:
    """并发给每条候选补相似问,再统一过滤。就地修改 `cs.candidates`。"""
    sem = asyncio.Semaphore(concurrency)

    async def one(cand: QaCandidate) -> tuple[list[str], LLMResult | None]:
        async with sem:
            try:
                return await gen_one(cand, n)
            except Exception as exc:
                # 单条失败不该毁掉整个抽取任务:那条没有改写,只是召回面窄一点,
                # 审核台上人还能自己补。整批失败才是真问题。
                log.warning(
                    "exact_qa_similar_failed",
                    question=cand.standard_question[:80],
                    error=f"{type(exc).__name__}: {exc}",
                )
                return [], None

    t0 = time.monotonic()
    pairs = await asyncio.gather(*(one(c) for c in cs.candidates))
    raw_lists = [p[0] for p in pairs]
    results = [p[1] for p in pairs if p[1] is not None]

    stats = filter_similar(cs.candidates, raw_lists)
    stats["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    stats["failed"] = len(cs.candidates) - len(results)
    log.info(
        "exact_qa_similar_done",
        items=len(cs.candidates),
        raw=stats["raw"],
        kept=stats["kept"],
        drop_same=stats["drop_same_as_standard"],
        drop_conflict=stats["drop_conflict"],
        failed=stats["failed"],
        elapsed_ms=stats["elapsed_ms"],
    )
    return stats, results
