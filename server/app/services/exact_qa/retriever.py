"""M4 命中判定:阈值 → 区分性 token 护栏 → light 模型复核,三段式。

实测结论见 documents/S1-PLAN.md §5 M4(27 条人写评测集:纯阈值 21/27 →
+护栏 23/27 → **+复核 26/27**,正例零误杀)。集成换两处:
numpy 内存索引 → pgvector(见 `indexer.py`)、openai 直调 → Provider light tier。

★ **为什么需要三段而不是一个阈值**(这是 S1 最值得讲的实测结论):

| 类别 | 余弦分数区间 | 阈值能不能切开 |
| --- | --- | --- |
| 正例(真实问法的改写) | 0.613 – 0.912 | — |
| 越界负例(问工资、问运费) | 0.129 – 0.384 | ✅ 一刀切干净 |
| 困难负例(同领域但原文没答案) | 0.613 – 0.827 | ❌ **与正例完全重叠** |

抬阈值买不到精度:抬到 0.75 只挡掉 3/5 困难负例,正例从 14 掉到 8。
所以补两道**与阈值正交**的关:

1. **区分性 token 护栏**(纯代码,零成本零延迟):查询里的含数字 token 不在命中面里 → 降级。
   实测拦下 2 条、零误伤,含最危险的那条 ——「416×416 的 mAP」以 **0.827** 命中
   「320×320」那条,只差一个数字,任何阈值都拦不住。
2. **light 模型命中复核**(只在"即将命中"时调一次,未命中的查询不付这笔钱):
   挡下另外 3 条纯语义邻近的困难负例(如「训练要多久」命中「用了哪些训练技巧」,0.72)——
   没有数字差异,护栏管不着,只有读一遍答案才判得出。

BORDERLINE 在 S1 按未命中处理(落回生成),但**必须 @traced 记分数/命中面/否决理由** ——
那是后续调阈值的唯一依据。
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models import (
    AgentKbBinding,
    ExactQaItem,
    ExactQaVector,
    KnowledgeBase,
    StagingItem,
)
from app.providers import LLMResult, get_embedder
from app.schemas.exact_qa import (
    HitTier,
    OriginRef,
    RetrievalCandidate,
    RetrievalResult,
)
from app.services.exact_qa.llm import parse_structured
from app.services.exact_qa.matching import salient_mismatch

log = get_logger(__name__)

#: 检索取回几个问题面。5 足够:分档只看 top1,其余是给 trace 面板看"差多少"的
TOP_K = 5
GATE_MAX_TOKENS = 512


# ------------------------------------------------------ 分档(纯函数,可离线测)


def decide_tier(
    best_score: float | None,
    *,
    guard_missing: set[str] | None = None,
    hit_threshold: float | None = None,
    borderline_threshold: float | None = None,
) -> HitTier:
    """三段式判定的**前两段**(阈值 + 护栏);第三段复核是异步的,在 `gate_hit()`。

    ★ 这个函数改错了不报错、只是静默把错答案标成 Verified Answer(或把正例挡在门外),
    所以有离线单测守着边界(`tests/test_exact_qa_retriever.py`)。
    """
    hit = settings.exact_qa_hit_threshold if hit_threshold is None else hit_threshold
    borderline = (
        settings.exact_qa_borderline_threshold
        if borderline_threshold is None
        else borderline_threshold
    )
    if best_score is None or best_score < borderline:
        return HitTier.MISS
    if best_score >= hit and not guard_missing:
        return HitTier.HIT
    # 分数够但区分性 token 对不上 → 降级,宁可落回生成模型也不返回错的"已验证答案"
    return HitTier.BORDERLINE


# --------------------------------------------------------- 命中复核(light 模型)

GATE_PROMPT = """\
You are the last gate before a knowledge base returns a stored answer to a user, labelled to the \
user as a verified answer. The answer was written and approved by a human reviewer, so its wording \
and level of detail are already settled. Decide one thing only: is the stored answer about the \
thing the user asked about?

Answer `false` when the stored answer is about a neighbouring but different thing — a different \
model, resolution, metric, product or entity — or when it addresses a different aspect than the \
one the user asked for, so a reader would be misled.

Do NOT answer `false` merely because the answer is short, plain, hedged or uncertain, omits detail \
the user did not ask for, or states less than you happen to know about the topic. A brief or \
uncertain answer to the right question is still the right answer; grading its quality is the human \
reviewer's job, not yours. Judge the answer text alone — you may not assume any fact that is not \
written in it. When the *topic* is genuinely in doubt, answer `false`: falling back to a normal \
generated reply is far cheaper than presenting a wrong answer as verified.
"""


class GateVerdict(BaseModel):
    """light 模型的复核结论(结构化输出)。"""

    answers_the_question: bool
    reason: str = Field(description="one short clause")


async def gate_hit(
    query: str, question: str, answer: str
) -> tuple[GateVerdict, LLMResult | None]:
    """复核一次"这答案答的是这个问题吗"。

    **失败时判通过而不是判否决**:复核是精度加成,不该让一次 LLM 抖动把
    本来正确的命中变成未命中(那会让演示时好好的正例突然不带标注)。
    """
    try:
        verdict, result = await parse_structured(
            GateVerdict,
            instructions=GATE_PROMPT,
            user_input=(
                f"User question: {query}\nStored question: {question}\nStored answer: {answer}"
            ),
            tier="light",
            max_tokens=GATE_MAX_TOKENS,
        )
        return verdict, result
    except Exception as exc:
        log.warning("exact_qa_gate_failed", error=f"{type(exc).__name__}: {exc}")
        return GateVerdict(answers_the_question=True, reason="gate unavailable"), None


# ---------------------------------------------------------------- pgvector 检索


async def _origin_ref_of(session: AsyncSession, item: ExactQaItem) -> OriginRef | None:
    """命中条目的原文出处。

    `exact_qa_items` 上刻意**没有** origin_ref 列 —— 出处是"这条知识从哪来"的溯源信息,
    已经存在它来源的那条 `staging_items.origin_ref` 里(`source_staging_id` 指过去)。
    再复制一份到正式表就多了一处会不同步的数据。
    """
    if item.source_staging_id is None:
        return None
    staging = await session.get(StagingItem, item.source_staging_id)
    if staging is None or not staging.origin_ref:
        return None
    try:
        return OriginRef.model_validate(staging.origin_ref)
    except ValidationError:
        # 老数据/手改过的 origin_ref 不该让整条问答链路失败,顶多少一个引用
        log.warning("exact_qa_origin_ref_invalid", item_id=str(item.id))
        return None


async def agent_exact_qa_kb_ids(session: AsyncSession, agent_id: uuid.UUID) -> list[uuid.UUID]:
    """这个 Agent 绑了哪些 exact_qa 知识库(只算 enabled 的绑定)。

    问答链路按绑定过滤,而不是"库里所有已采纳的 QA 都能被任何 Agent 命中" ——
    否则多 Agent 演示时会互相串味,而且 S4 的路由也无从谈起。
    """
    rows = (
        await session.execute(
            select(AgentKbBinding.kb_id)
            .join(KnowledgeBase, KnowledgeBase.id == AgentKbBinding.kb_id)
            .where(
                AgentKbBinding.agent_id == agent_id,
                AgentKbBinding.enabled.is_(True),
                KnowledgeBase.type == "exact_qa",
                KnowledgeBase.status == "active",
            )
        )
    ).all()
    return [r[0] for r in rows]


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    kb_ids: list[uuid.UUID] | None = None,
    top_k: int = TOP_K,
    use_gate: bool | None = None,
) -> tuple[RetrievalResult, list[LLMResult]]:
    """一次完整检索:embedding → pgvector top-k → 三段式判定。

    余弦相似度 = `1 - cosine_distance`。**距离算子必须是 cosine**
    (HNSW 索引也建在 `vector_cosine_ops` 上):换成 L2 分数会静默偏移,
    Step 5 调出来的阈值全部作废 —— 这是"内存索引换 pgvector"唯一真会出错的地方。
    """
    gate_on = settings.exact_qa_hit_gate if use_gate is None else use_gate
    if kb_ids is not None and not kb_ids:
        # 这个 Agent 没绑任何精准 QA 库 → 不该命中任何东西,也别白付一次 embedding
        return RetrievalResult(query=query, tier=HitTier.MISS), []
    qvec = (await get_embedder().embed([query]))[0]

    distance = ExactQaVector.embedding.cosine_distance(qvec)
    stmt = (
        select(
            ExactQaVector.item_id,
            ExactQaVector.question_text,
            distance.label("distance"),
            ExactQaItem.standard_question,
        )
        .join(ExactQaItem, ExactQaItem.id == ExactQaVector.item_id)
        .where(ExactQaItem.status == "enabled")
        .order_by(distance)
        .limit(top_k)
    )
    if kb_ids is not None:
        stmt = stmt.where(ExactQaItem.kb_id.in_(kb_ids))
    # 有效期过滤:NULL = 不限(生效日/失效日都由采纳的人可选地填)
    today = date.today()
    stmt = stmt.where(
        or_(ExactQaItem.effective_from.is_(None), ExactQaItem.effective_from <= today),
        or_(ExactQaItem.effective_to.is_(None), ExactQaItem.effective_to >= today),
    )

    rows = (await session.execute(stmt)).all()
    top = [
        RetrievalCandidate(
            item_id=str(item_id),
            question_text=face,
            is_standard=face == std,
            score=1.0 - float(dist),
        )
        for item_id, face, dist, std in rows
    ]

    best = top[0] if top else None
    guard_missing = salient_mismatch(query, best.question_text) if best else set()
    tier = decide_tier(best.score if best else None, guard_missing=guard_missing)

    result = RetrievalResult(
        query=query,
        tier=tier,
        top=top,
        guard_missing=sorted(guard_missing),
    )
    if best is None:
        return result, []

    item = await session.get(ExactQaItem, uuid.UUID(best.item_id))
    if item is None:  # 理论上不会:向量行有 ON DELETE CASCADE
        result.tier = HitTier.MISS
        return result, []

    usages: list[LLMResult] = []
    if result.tier is HitTier.HIT and gate_on:
        verdict, llm_result = await gate_hit(query, best.question_text, item.answer)
        if llm_result is not None:
            usages.append(llm_result)
        if not verdict.answers_the_question:
            # 复核否决 → 不打 Verified Answer,落回生成。理由必须留下:调阈值只能看它
            result.tier = HitTier.BORDERLINE
            result.gate_reason = verdict.reason

    if result.tier is HitTier.HIT:
        result.answer = item.answer  # ★ 零改写:命中就原样返回,不过生成模型
        result.origin_ref = await _origin_ref_of(session, item)

    log.info(
        "exact_qa_retrieved",
        query=query[:80],
        tier=result.tier.value,
        best_score=round(best.score, 4),
        faces=len(top),
        guard_missing=result.guard_missing or None,
        gate_reason=result.gate_reason,
    )
    return result, usages
