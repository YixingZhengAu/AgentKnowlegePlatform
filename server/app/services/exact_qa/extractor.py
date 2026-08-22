"""M2 候选 QA 抽取:校对后的 markdown → 候选 QA 列表(带原文出处)。

实测结论见 documents/S1-PLAN.md §5 M2(prompt 调了三轮,39 → 36 条)。
集成只换一处:openai 直调 → Provider 层 main tier。**prompt 与过滤逻辑一字不改**。

质量硬约束在本层落地(不合格的不进候选列表,丢弃原因计数入 stats):
答案为空 / 无原文引用 / quote 在源文本里定位不到 / 标准问重复。

实测踩过的三个坑(都已固化成代码,不要"简化"掉):
1. **quote 定位要带修复**:模型爱把 `AP<sub>50</sub>` / `$x , y$` 这类排版标记改写掉,
   整段匹配就失败。二分取"能对上的最长前缀"(≥40 字符),实测 quote_not_found 从 6 降到 1。
2. **逐字 quote 校验能拦事实性错抄**:拦下过一条把公式里 σ(t_x) 抄成 c(t_x) 的候选。
3. **判重不能只看词集 Jaccard**(见 `matching.py` 的注释),否则静默丢知识。

注意:prompt 与产出的 QA 内容一律英文(平台面向澳洲用户,无 i18n);中文只在注释里。
"""

import re
import time
from collections import Counter

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.providers import LLMResult
from app.schemas.exact_qa import (
    ContentBlock,
    DropReason,
    ExtractStats,
    OriginRef,
    QaCandidate,
    QaCandidateSet,
)
from app.services.exact_qa.llm import parse_structured
from app.services.exact_qa.matching import is_near_duplicate, normalize

log = get_logger(__name__)

#: 单次抽取喂给模型的最大字符数;超了按页切段,分段抽取再合并
#: (实测 sample-paper-3p 的 14943 字符切成 2 段,每段一次调用)
DEFAULT_MAX_CHARS = 9000

#: 一次抽取给模型的回答预算。抽 5–20 条带 quote 的 QA 很占 token,给小了会被截断
MAX_TOKENS = 8192

#: quote 修复的最短可接受长度:短于此的片段在审核台上没有对照价值
MIN_QUOTE_CHARS = 40

PAGE_MARKER_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")


# ------------------------------------------------------- LLM 结构化输出的形状


class LlmQaItem(BaseModel):
    """LLM 直接产出的一条(不含 bbox —— bbox 由我们用 content_list 回填)。"""

    standard_question: str
    answer: str
    keywords: list[str]
    quote: str = Field(description="verbatim excerpt from the source text")
    page_idx: int
    confidence: float


class LlmQaList(BaseModel):
    items: list[LlmQaItem]


SYSTEM_PROMPT = """\
You build a verified-answer knowledge base for an enterprise Q&A assistant.

From the given document excerpt, extract question–answer pairs that a real user would ask \
and that the excerpt answers **explicitly**. Each pair must stand on its own, with no \
reference to "this document", "the paper", "the table above", "Section 2" or similar.

Rules:
1. `standard_question` — one natural, self-contained question in English. Name the subject \
explicitly (e.g. "What backbone network does YOLOv3 use?", never "What backbone does it use?").
2. `answer` — the factual answer, stated directly and completely, in 1–3 sentences. Include the \
concrete numbers, names and units from the source. Never answer with a pointer such as \
"see Table 1". Never invent anything that is not in the excerpt. The answer must be as \
self-contained as the question: no referential phrases such as "this metric", "that figure" or \
"the table above" — name the metric, figure or subject outright.
3. `quote` — a **verbatim** span copied character-for-character from the excerpt that contains the \
answer. Do not paraphrase, do not fix typos, do not join distant sentences. Keep it under 400 \
characters. If you cannot copy an exact span, drop the pair.
4. `page_idx` — the integer from the nearest preceding `<!-- page: N -->` marker of the quote.
5. `keywords` — 2–5 short retrieval keywords (entities, model names, metrics).
6. `confidence` — 0.0–1.0: how directly and unambiguously the excerpt states the answer.
7. Prefer facts that stay true out of context: definitions, architectures, measured numbers, \
comparisons, design decisions, limitations. Skip jokes, acknowledgements, citations, running \
prose with no factual payload, and anything you would have to guess at.
8. Tables are a rich source, but parsing may have mangled them. Only extract a table fact when \
the row/column association is unambiguous in the markup you see.
9. Do not emit two pairs whose answers say substantially the same thing. If one fact supports \
several phrasings, keep the single most complete pair — rephrasings are generated separately later.
Return between 5 and 20 pairs for this excerpt. Fewer good pairs beats more shaky ones.
"""


# ------------------------------------------------------------------ 文本切段


def split_by_pages(md: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """按页标记切段,再把连续页合并到 max_chars 以内。

    切在页边界上,保证每段都带 `<!-- page: N -->`,模型才填得出 page_idx。
    """
    parts = PAGE_MARKER_RE.split(md)
    # split 结果:[前言, 页码, 内容, 页码, 内容, ...]
    pages: list[str] = []
    for i in range(1, len(parts), 2):
        pages.append(f"<!-- page: {parts[i]} -->\n{parts[i + 1].strip()}")
    if not pages:
        return [md]

    chunks: list[str] = []
    cur = ""
    for page in pages:
        if cur and len(cur) + len(page) > max_chars:
            chunks.append(cur)
            cur = page
        else:
            cur = f"{cur}\n\n{page}" if cur else page
    if cur:
        chunks.append(cur)
    return chunks


# ------------------------------------------------------- quote 定位与 bbox 回填


def repair_quote(quote: str, normalized_md: str) -> str | None:
    """quote 整段定位不到时,取它在源文本里能对上的**最长前缀**。

    模型常在句尾把两处文字接在一起,或把 LaTeX / 排版符号顺手改写掉,导致整段匹配失败。
    截到最长可对上的前缀,既保住"逐字摘录"的硬约束,又不白丢一条好候选。
    截不出 MIN_QUOTE_CHARS 以上的前缀才真丢弃。
    """
    lo, hi = MIN_QUOTE_CHARS, len(quote)
    best = 0
    while lo <= hi:  # 前缀长度单调,二分即可
        mid = (lo + hi) // 2
        if normalize(quote[:mid]) in normalized_md:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return quote[:best].strip() if best >= MIN_QUOTE_CHARS else None


def locate(
    quote: str, md: str, blocks: list[ContentBlock]
) -> tuple[str | None, int | None, list[int] | None]:
    """在源文本里定位 quote,并顺带回填 page_idx / bbox。

    返回 (定位到的逐字片段 or None, page_idx, bbox)。
    bbox 取"完整包含该片段的那个块"的框;片段跨块时给不出唯一框,bbox 为 None(契约允许)。
    """
    nmd = normalize(md)
    nq = normalize(quote)
    if not nq:
        return None, None, None
    if nq not in nmd:
        fixed = repair_quote(quote, nmd)
        if fixed is None:
            return None, None, None
        quote, nq = fixed, normalize(fixed)
    for b in blocks:
        text = b.text or b.table_body or ""
        if text and nq in normalize(text):
            return quote, b.page_idx, b.bbox
    return quote, None, None


# ---------------------------------------------------- 过滤(纯函数,可离线测)


def filter_candidates(
    document_id: str,
    raw: list[LlmQaItem],
    md: str,
    blocks: list[ContentBlock],
) -> tuple[list[QaCandidate], Counter[str], int]:
    """把 LLM 原始产出过成候选列表。返回 (保留的候选, 丢弃计数, quote 修复条数)。

    ★ 这个函数是 S1 唯一必须有离线单测的一类:输入输出确定,**改错了不报错、
    只是静默给出更少或更脏的知识**。见 `tests/test_exact_qa_extractor.py`。
    """
    dropped: Counter[str] = Counter()
    seen: list[str] = []
    repaired = 0
    kept: list[QaCandidate] = []

    for item in raw:
        if not item.answer.strip():
            dropped[DropReason.EMPTY_ANSWER] += 1
            continue
        if not item.quote.strip():
            dropped[DropReason.NO_ORIGIN_REF] += 1
            continue
        quote, page_idx, bbox = locate(item.quote, md, blocks)
        if quote is None:
            dropped[DropReason.QUOTE_NOT_FOUND] += 1
            continue
        if quote != item.quote.strip():
            repaired += 1
        if is_near_duplicate(item.standard_question, seen):
            dropped[DropReason.DUPLICATE_QUESTION] += 1
            continue
        seen.append(item.standard_question)
        kept.append(
            QaCandidate(
                standard_question=item.standard_question,
                answer=item.answer,
                keywords=item.keywords,
                origin_ref=OriginRef(
                    document_id=document_id,
                    # 以定位到的块页码为准,模型填的 page_idx 只作兜底
                    page_idx=page_idx if page_idx is not None else max(item.page_idx, 0),
                    quote=quote,
                    bbox=bbox,
                ),
                confidence=min(max(item.confidence, 0.0), 1.0),
            )
        )

    kept.sort(key=lambda c: (-c.confidence, c.origin_ref.page_idx))
    return kept, dropped, repaired


# ------------------------------------------------------------------- 抽取主体


async def extract_chunk(chunk: str) -> tuple[list[LlmQaItem], LLMResult]:
    parsed, result = await parse_structured(
        LlmQaList,
        instructions=SYSTEM_PROMPT,
        user_input=f"Document excerpt:\n\n{chunk}",
        tier="main",
        max_tokens=MAX_TOKENS,
    )
    return list(parsed.items), result


async def extract(
    *,
    document_id: str,
    source_md_name: str,
    md: str,
    blocks: list[ContentBlock],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[QaCandidateSet, list[LLMResult]]:
    """完整抽取:切段 → 逐段调 main 模型 → 硬约束过滤 + bbox 回填。

    返回的 `LLMResult` 列表交给调用方记账(Job 的 step 日志 / trace)。
    """
    chunks = split_by_pages(md, max_chars)
    t0 = time.monotonic()
    raw: list[LlmQaItem] = []
    results: list[LLMResult] = []
    model = ""
    for i, chunk in enumerate(chunks, 1):
        items, result = await extract_chunk(chunk)
        raw.extend(items)
        results.append(result)
        model = result.model
        log.info(
            "exact_qa_extract_chunk",
            document_id=document_id,
            chunk=f"{i}/{len(chunks)}",
            chars=len(chunk),
            items=len(items),
        )

    kept, dropped, repaired = filter_candidates(document_id, raw, md, blocks)
    log.info(
        "exact_qa_extracted",
        document_id=document_id,
        raw=len(raw),
        kept=len(kept),
        repaired=repaired,
        dropped=dict(dropped),
    )
    return (
        QaCandidateSet(
            document_id=document_id,
            source_md=source_md_name,
            candidates=kept,
            stats=ExtractStats(
                model=model,
                chunk_count=len(chunks),
                raw_count=len(raw),
                kept_count=len(kept),
                dropped=dict(dropped),
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            ),
        ),
        results,
    )
