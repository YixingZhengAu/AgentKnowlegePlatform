"""`run_chat()` —— 问答的唯一入口(D4:HTTP / SSE / 评测执行器共用一条链路)。

**单入口是怎么做到的**:真正的编排只有一个 async generator `chat_events()`,它永远产出事件流;
非流式的 `run_chat()` 只是把这个事件流消费到底再拼成 `ChatResult`。
所以"流式"和"非流式"不是两份代码 —— S1–S4 往编排里插阶段,两条路径同时生效,不可能只改到一边。

S1 / S3 之后的链路:

    加载 agent → 存用户消息 → [stage: retrieve_exact_qa] → 命中?
        命中 → 原样返回标准答案(**不调生成模型**)+ 写 message_citations + 标 Verified Answer
        未命中 → [stage: retrieve_text2sql](Agent 绑了问数库才跑)
            executed → 返回确定性结论 + 数据表格 + 最终 SQL(citation_type=sql),标 Verified
            refused_out_of_template → 直接返回拒答话术(**不让生成模型接手**)
            refused_non_data / 链路出错 → [stage: retrieve_doc_rag](Agent 绑了文档库才跑)
                有召回 → 把切片当证据拼进 prompt,生成时带引用
                零召回 → 继续走 [stage: generate] 调 LLM
    → 存回复 → flush traces

★ **命中时零改写、零生成调用**是 PRD 的零幻觉承诺落地的地方:答案是人工采纳过的原文,
不让模型碰它,连"润色一下"都不做 —— 一旦过生成模型,"已验证"这个标注就不成立了。
问数命中同理:结论那句话是**代码从结果集算出来的**,不是模型写的(自然语言叙述归 S4)。

★ 两种拒答的分岔是刻意的:模板外拒答(问对了域、超出了已验收模板)交给生成模型只会
换来一个听起来合理的编数;非问数拒答(检索层零 LLM 就判掉了)本来就该由别的链路接手。

S4 插 `route` 同理:往这里加一个 `async with traced(...)` 块,
**事件协议只增加事件类型,不改已有事件的形状**(S1 新增 `verified` 事件,
`done` 新增 `verified` 布尔字段与真正有内容的 `citations`;S3 复用同两个事件,
只是 `verified.source` 变成 `text2sql`、引用类型变成 `sql`)。
"""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.core.trace import ChatContext, TraceSpan, flush_traces, spans_as_dicts, traced
from app.db import SessionLocal
from app.models import Agent, Conversation, Message, MessageCitation, User
from app.models.user import DEFAULT_USERNAME
from app.providers import ChatMessage, get_llm
from app.schemas.exact_qa import HitTier, RetrievalResult
from app.services.document import retriever as doc_rag
from app.services.document import verifier as doc_verifier
from app.services.exact_qa.retriever import agent_exact_qa_kb_ids, retrieve
from app.services.text2sql import runtime as t2s

log = get_logger(__name__)

# 带进 prompt 的历史条数(user / assistant 各算一条)
HISTORY_LIMIT = 10
# 会话标题:首问截断
TITLE_MAX = 60
DEFAULT_FALLBACK = "Sorry, I could not generate an answer just now. Please try again."

# 被 detach 出去的落库任务:必须持引用,否则可能被 GC 掉(asyncio 只持弱引用)
_BACKGROUND: set[asyncio.Task] = set()


def _detach(coro: Coroutine[Any, Any, Any], *, name: str) -> None:
    """把一个协程扔到后台跑,并保住引用。用于"请求已被取消,但这件事还得做完"。"""
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


@dataclass(slots=True)
class ChatEvent:
    """SSE 事件。`event` 就是 SSE 的 event 名,`data` 序列化成 JSON。"""

    event: str
    data: dict


@dataclass(slots=True)
class ChatResult:
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    content: str
    status: str
    usage: dict
    cost_usd: Decimal
    latency_ms: int
    citations: list[dict] = field(default_factory=list)
    # 这条回答是不是"人工采纳过的标准答案原样返回"(前端据此打 Verified Answer 标注)
    verified: bool = False
    trace: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------- 加载与落库


async def _load_user(session: AsyncSession, user_id: uuid.UUID | None) -> User:
    """S0–S5 没有用户体系:不传就取 seed 出来的 default_user。"""
    if user_id is not None:
        user = await session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user
    user = (
        await session.execute(select(User).where(User.username == DEFAULT_USERNAME))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"默认用户 {DEFAULT_USERNAME} 不存在,请先执行 make seed")
    return user


async def _load_agent(session: AsyncSession, agent_id: uuid.UUID) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.status != "active":
        raise NotFoundError(f"Agent {agent_id} not found")
    return agent


async def _get_or_create_conversation(
    session: AsyncSession,
    *,
    agent: Agent,
    user: User,
    conversation_id: uuid.UUID | None,
    question: str,
) -> Conversation:
    if conversation_id is not None:
        conv = await session.get(Conversation, conversation_id)
        if conv is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conv
    # 不传 conversation_id 就新开一轮:前端"新对话"不需要先调一次建会话接口
    conv = Conversation(agent_id=agent.id, user_id=user.id, title=question.strip()[:TITLE_MAX])
    session.add(conv)
    await session.flush()
    return conv


async def _history(session: AsyncSession, conversation_id: uuid.UUID) -> list[ChatMessage]:
    """取最近 N 条消息(倒序取、正序用)。失败/中断的助手消息不进 prompt。"""
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.status == "completed")
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


async def _persist(
    ctx: ChatContext,
    *,
    content: str,
    status: str,
    question: str,
    citations: list[dict] | None = None,
) -> None:
    """助手消息 + trace 落库。**自己开 session**:

    中断路径要在"请求已被取消"之后再落库,那时原来的 session 所属任务已经死了,
    只有一个独立 session 才做得成这件事。顺序不能反 —— traces 的外键指向这条消息。
    """
    async with SessionLocal() as session:
        usage = ctx.total_usage
        session.add(
            Message(
                id=ctx.message_id,
                conversation_id=ctx.conversation_id,
                role="assistant",
                content=content,
                status=status,
                usage={**usage.as_dict(), "cost_usd": str(ctx.total_cost)},
                latency_ms=ctx.total_latency_ms,
            )
        )
        await session.flush()
        for c in citations or []:
            session.add(
                MessageCitation(
                    message_id=ctx.message_id,
                    seq=c["seq"],
                    citation_type=c["citation_type"],
                    ref_id=uuid.UUID(c["ref_id"]) if c.get("ref_id") else None,
                    snippet=c.get("snippet"),
                    extra=c.get("extra") or {},
                )
            )
        n = await flush_traces(session, ctx)
        conv = await session.get(Conversation, ctx.conversation_id)
        if conv is not None:
            conv.last_message_at = datetime.now(UTC)
            if not conv.title:
                conv.title = question.strip()[:TITLE_MAX]
        await session.commit()
    log.info(
        "chat_persisted",
        message_id=str(ctx.message_id),
        status=status,
        traces=n,
        citations=len(citations or []),
        **usage.as_dict(),
        cost_usd=str(ctx.total_cost),
    )


# ---------------------------------------------------------------- 精准 QA 命中(S1)

#: stage 名。前端轨迹面板按 stage 名分组,改名等于改公共契约
STAGE_EXACT_QA = "retrieve_exact_qa"
#: 问数链路的第一个 stage(后面两个 stage 名由 pipeline.trace_events() 给出:
#: rewrite_sql / execute_sql)。三个合起来就是 trace 五要素
STAGE_TEXT2SQL = "retrieve_text2sql"
#: 文档 RAG 的 stage(S2)。它是串行兜底的最后一棒:前两条都没命中才跑
STAGE_DOC_RAG = "retrieve_doc_rag"

#: 生成后校验的 stage 名(只有 DOC_RAG_VERIFY=true 时才出现在轨迹里)
STAGE_DOC_VERIFY = "verify_doc_rag"


def _retrieval_trace(result: RetrievalResult) -> dict:
    """★ 落 trace 的内容:分数 + 命中面 + 两道关的否决理由。

    BORDERLINE 也必须留下这些(S1-plan §5 M5)—— 它们是后续调阈值的**唯一**依据。
    只记"未命中"的话,以后既不知道差多少,也不知道是被哪道关挡下的。
    """
    return {
        "tier": result.tier.value,
        "best_score": round(result.top[0].score, 4) if result.top else None,
        "best_face": result.top[0].question_text if result.top else None,
        "top": [
            {"score": round(c.score, 4), "face": c.question_text, "standard": c.is_standard}
            for c in result.top
        ],
        "guard_missing": result.guard_missing or None,
        "gate_reason": result.gate_reason,
    }


def _exact_qa_citations(result: RetrievalResult) -> list[dict]:
    """命中 → 一条 exact_qa 引用。**强制引用**:命中必须能点回原文(PRD 的硬要求)。"""
    if not result.top:
        return []
    best = result.top[0]
    origin = result.origin_ref
    return [
        {
            "seq": 1,
            "citation_type": "exact_qa",
            "ref_id": best.item_id,
            "snippet": origin.quote if origin else best.question_text,
            "extra": {
                "score": round(best.score, 4),
                "matched_question": best.question_text,
                "is_standard_question": best.is_standard,
                "document_id": origin.document_id if origin else None,
                "page_idx": origin.page_idx if origin else None,
                "bbox": origin.bbox if origin else None,
            },
        }
    ]


# ---------------------------------------------------------------- 文档 RAG(S2)

#: 证据块的最大字符数 —— 5 片 × 512 token 已经不小,再多会挤掉历史对话
DOC_RAG_SNIPPET_CHARS = 240

#: 🩸 **哨兵句**:材料答不了时模型必须原样回这一句。它有两个身份 ——
#: ① 用户看到的兜底话术(每次拒答措辞一致,演示可预期);
#: ② 后端判定"零引用"的判据(见 `_doc_rag_used`)。
#: 判据因此是一次字符串比对,不是关键词猜测,也不用再多付一次 LLM 调用。
#: 措辞改了就得同步 `documents/S2-PLAN.md` C4(引用入选规则)。
DOC_RAG_NO_EVIDENCE = "I could not find support for this in the available documents."

DOC_RAG_INSTRUCTION = (
    "Answer the question using only the excerpts below. "
    "Cite the excerpt number in square brackets after each claim, e.g. [1]. "
    "If the excerpts do not contain the answer, reply with exactly this sentence "
    f"and nothing else: {DOC_RAG_NO_EVIDENCE}"
)

#: 答案正文里的引用标记。上限两位数:我们最多给 5 片,三位数的一定是原文自带的文献号
_CITATION_MARK = re.compile(r"\[(\d{1,2})\]")


def _doc_rag_context(hits: list[doc_rag.DocRagHit]) -> ChatMessage:
    """把召回的切片拼成一条 system 消息 —— 生成模型的唯一证据来源。

    编号从 1 起,与 `_doc_rag_citations` 的 `seq` 对齐:
    模型写的 `[2]` 与引用面板的第 2 条必须是同一片,否则点回原文会点错。
    """
    blocks = []
    for i, h in enumerate(hits, 1):
        where = f"{h.doc_name} — {h.heading_path}" if h.heading_path else h.doc_name
        blocks.append(f"[{i}] {where} (page {h.page_idx + 1})\n{h.content}")
    return {"role": "system", "content": DOC_RAG_INSTRUCTION + "\n\n" + "\n\n".join(blocks)}


def _doc_rag_used(content: str, citations: list[dict]) -> list[dict]:
    """按答案正文挑出**真正被引用**的那几条(分册 3 §3b「区分派」)。

    🩸 **定编号 ≠ 定入选**。编号在拼 prompt 时就定死(不让模型自己编号,防错位),
    但"哪几条该出现在引用面板上"要看答案实际站在哪几片上 ——
    把 Top-5 无条件全挂,等于告诉用户"这句话有 5 个出处",而它可能只用了 1 个。

    三种情形:
    - 正文里有编号 → 只留出现过的,**编号不重排**(重排会让正文的 `[3]` 指向面板第 2 条);
    - 没有编号,但答案是哨兵句(模型明说没找到依据)→ **零引用**;
    - 没有编号,答案却有实质内容 → **保底留 Top-1**。短答案上模型偶尔忘标编号,
      而把一个有据的答案显示成"无出处",比多显示一条最相关的材料更糟。

    Args:
        content: 生成模型的完整回答。
        citations: `_doc_rag_citations()` 给出的候选引用(seq 与 prompt 里的编号一致)。

    Returns:
        要落库的引用子集;`citations` 为空时恒为空。
    """
    if not citations:
        return []

    valid = {c["seq"] for c in citations}
    marks = {int(m) for m in _CITATION_MARK.findall(content)}
    if unknown := sorted(marks - valid):
        # 模型引了不存在的编号(或照抄了原文自带的文献号)—— 丢掉,但要看得见
        log.warning("doc_rag_citation_out_of_range", marks=unknown, available=sorted(valid))

    if used := [c for c in citations if c["seq"] in marks]:
        return used
    if DOC_RAG_NO_EVIDENCE.rstrip(".") in content:
        return []
    return citations[:1]


def _doc_rag_citations(hits: list[doc_rag.DocRagHit]) -> list[dict]:
    """把每条召回做成一条**候选**引用(真正落哪几条由 `_doc_rag_used` 决定)。"""
    return [
        {
            "seq": i,
            "citation_type": "chunk",
            "ref_id": str(h.chunk_id),
            "snippet": h.content[:DOC_RAG_SNIPPET_CHARS],
            "extra": {
                "score": round(h.score, 4),
                "document_id": str(h.doc_id),
                "document_name": h.doc_name,
                "page_idx": h.page_idx,
                "heading_path": h.heading_path,
                "seq_in_doc": h.seq,
                "rank_vector": h.rank_vector,
                "rank_fts": h.rank_fts,
                "figures": h.figures,
            },
        }
        for i, h in enumerate(hits, 1)
    ]


def _doc_rag_trace(hits: list[doc_rag.DocRagHit], trace: doc_rag.DocRagTrace) -> dict:
    """轨迹面板要如实显示真实发生的事:两条腿各召回多少、融合多少、最后留几条。"""
    return {
        "recall": {"vector": trace.vector_hits, "fts": trace.fts_hits, "fused": trace.fused},
        "reranked": trace.reranked,
        "hits": [
            {
                "chunk_id": str(h.chunk_id),
                "document": h.doc_name,
                "heading_path": h.heading_path,
                "page_idx": h.page_idx,
                "score": round(h.score, 4),
                "rank_vector": h.rank_vector,
                "rank_fts": h.rank_fts,
            }
            for h in hits
        ],
    }


# ---------------------------------------------------------------- 命中路径的收尾


async def _finish(
    ctx: ChatContext,
    *,
    conv_id: uuid.UUID,
    question: str,
    content: str,
    citations: list[dict],
    verified: bool,
) -> AsyncIterator[ChatEvent]:
    """命中路径的收尾:token → 落库 → done。**两条命中链路共用**(精准问答 / 问数)。

    抽出来不是为了少写几行,是为了保证两条链路的**事件顺序与 done 的字段完全一样** ——
    前端只有一条渲染路径,一旦哪条链路少给一个字段,那是只在某种问题上才复现的 bug。
    """
    # 命中也走 token 事件:前端只有一条渲染路径(与失败兜底同一个理由)
    yield ChatEvent("token", {"text": content})
    await _persist(ctx, content=content, status="completed", question=question,
                   citations=citations)
    yield ChatEvent(
        "done",
        {
            "message_id": str(ctx.message_id),
            "conversation_id": str(conv_id),
            "status": "completed",
            "usage": ctx.total_usage.as_dict(),
            "cost_usd": str(ctx.total_cost),
            "latency_ms": ctx.total_latency_ms,
            "citations": citations,
            "verified": verified,
            "trace": spans_as_dicts(ctx.spans),
            "error": None,
        },
    )


# ---------------------------------------------------------------- 智能问数(S3)


def _t2s_spans(
    ctx: ChatContext, result: dict, head: TraceSpan, usages: list
) -> None:
    """把链路摊成三个 trace span(五要素:意图分数 / 模板 id / 计划 / 最终 SQL / 行数+耗时)。

    ★ 为什么不是三个 `async with traced(...)`:编排在 `pipeline.answer()` 里面,
      它是被评测集守着的代码(`make smoke-s3`),不该为了埋点被拆开。它已经逐段计了时,
      所以这里按 `trace_events()` 给出的形状**照抄**即可 —— 埋点字段的出处只有那一个。

    两处必须自己动手的:

    * **`head` 的耗时要改成"只有检索那一段"**。`traced()` 量的是整条链路,直接留着的话
      它和后两个 span 相加会把总耗时算成两倍(`ChatContext.total_latency_ms` 是求和)。
    * **LLM 的账记在 `rewrite_sql` 上**,不记在检索那一段 —— 唯一一次模型调用是改写计划。
      非问数问题没有 rewrite span,于是也没有账:那正是"检索层拒答零成本"的机器可证形式。
    """
    events = t2s.trace_events(result)
    head.output = events[0]["output"]
    head.latency_ms = events[0]["latency_ms"]
    for ev in events[1:]:
        span = TraceSpan(stage=ev["stage"], seq=ctx.next_seq(),
                         latency_ms=ev["latency_ms"], output=ev["output"])
        if ev["stage"] == "rewrite_sql":
            for usage in usages:
                span.record_llm(usage)
        ctx.spans.append(span)


# ---------------------------------------------------------------- 编排


async def chat_events(
    *,
    agent_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> AsyncIterator[ChatEvent]:
    """问答编排(唯一实现)。自己开 session —— SSE 的生成器不依赖请求作用域的依赖注入。"""
    llm = get_llm()

    async with SessionLocal() as session:
        agent = await _load_agent(session, agent_id)
        user = await _load_user(session, user_id)
        conv = await _get_or_create_conversation(
            session, agent=agent, user=user, conversation_id=conversation_id, question=question
        )
        history = await _history(session, conv.id)
        # 用户消息先落库并提交:后面生成失败了,问题也不会丢(未命中问题池要用它)
        session.add(Message(conversation_id=conv.id, role="user", content=question))
        await session.commit()
        conv_id = conv.id
        system_prompt = agent.system_prompt
        fallback = agent.fallback_reply or DEFAULT_FALLBACK
        temperature = float(agent.model_cfg.get("temperature", 0.3))

    # 助手消息 id 预生成:所有 stage 的 trace 都挂在它下面
    ctx = ChatContext(message_id=uuid.uuid4(), agent_id=agent_id, conversation_id=conv_id)
    yield ChatEvent("meta", {"message_id": str(ctx.message_id), "conversation_id": str(conv_id)})

    prompt: list[ChatMessage] = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": question},
    ]

    parts: list[str] = []
    content = ""
    status = "completed"
    error: str | None = None
    final = None
    citations: list[dict] = []
    #: 拼进 prompt 的那段文档证据(原样留一份给生成后校验),没召回时是 None
    doc_evidence: str | None = None
    verified: RetrievalResult | None = None

    try:
        # ---- stage: retrieve_exact_qa(S1)
        # 检索失败绝不能弄死一次问答:退化成"没命中",照常走生成
        yield ChatEvent("stage_start", {"stage": STAGE_EXACT_QA})
        try:
            async with traced(ctx, STAGE_EXACT_QA, input={"question": question}) as span:
                async with SessionLocal() as session:
                    kb_ids = await agent_exact_qa_kb_ids(session, agent_id)
                    result, gate_usages = await retrieve(session, question, kb_ids=kb_ids)
                for usage in gate_usages:  # light 模型复核的账也要记
                    span.record_llm(usage)
                span.output = _retrieval_trace(result)
                if result.tier is HitTier.HIT:
                    verified = result
        except Exception as exc:
            log.warning("chat_exact_qa_failed", agent_id=str(agent_id), error=str(exc))
            yield ChatEvent("error", {"stage": STAGE_EXACT_QA, "message": str(exc)})
        yield ChatEvent(
            "stage_end", {**spans_as_dicts(ctx.spans)[-1], "stage": STAGE_EXACT_QA}
        )

        if verified is not None:
            # ★ 命中:原样返回人工采纳过的答案,**不调生成模型**(零改写才敢叫已验证)
            content = verified.answer or ""
            citations = _exact_qa_citations(verified)
            parts.append(content)
            yield ChatEvent(
                "verified",
                {
                    "source": "exact_qa",
                    "score": citations[0]["extra"]["score"] if citations else None,
                    "matched_question": citations[0]["extra"]["matched_question"]
                    if citations
                    else None,
                    "citations": citations,
                },
            )
            async for ev in _finish(ctx, conv_id=conv_id, question=question,
                                    content=content, citations=citations, verified=True):
                yield ev
            return

        # ---- stage: retrieve_text2sql(S3)
        # 只在 Agent 绑了 text2sql 库、且库里有已发布意图时才跑。**没绑就一个事件都不发** ——
        # 只绑了精准问答的 Agent,它的事件流与 S1 时代逐字相同,轨迹面板上不会多出空阶段。
        async with SessionLocal() as session:
            t2s_kb_ids = await t2s.agent_text2sql_kb_ids(session, agent_id)
            t2s_ctx = await t2s.load_runtime(session, t2s_kb_ids) if t2s_kb_ids else None

        if t2s_ctx is not None:
            data: dict | None = None
            yield ChatEvent("stage_start", {"stage": STAGE_TEXT2SQL})
            base = len(ctx.spans)
            try:
                async with traced(
                    ctx, STAGE_TEXT2SQL, input={"question": question}
                ) as span:
                    data, t2s_usages = await t2s.answer(question, t2s_ctx)
                _t2s_spans(ctx, data, span, t2s_usages)
            except Exception as exc:
                # 与精准问答同一条纪律:检索/执行出错绝不能弄死一次问答,退化成"没命中"
                log.warning("chat_text2sql_failed", agent_id=str(agent_id), error=str(exc))
                yield ChatEvent("error", {"stage": STAGE_TEXT2SQL, "message": str(exc)})
            for sd in spans_as_dicts(ctx.spans)[base:]:
                if sd["stage"] != STAGE_TEXT2SQL:
                    yield ChatEvent("stage_start", {"stage": sd["stage"]})
                yield ChatEvent("stage_end", sd)

            outcome = (data or {}).get("outcome")
            if outcome == "execution_failed":
                # ★ 永远算 bug,不是业务边界。记响一点,然后退回生成 ——
                # 让生成模型接手一个"本该有准确数字"的问题不理想,但比整条问答挂掉好
                log.error("chat_text2sql_execution_failed", agent_id=str(agent_id),
                          intent=data.get("intent_id"), error=data.get("execution_error"))
                yield ChatEvent("error", {"stage": "execute_sql",
                                          "message": data.get("execution_error") or "unknown"})
            elif outcome == "executed":
                # ★ 结论那句话是代码从结果集算出来的,没过生成模型 —— 所以敢标 Verified
                content = data["reply"] or ""
                citations = t2s.citations(data, t2s_ctx)
                parts.append(content)
                yield ChatEvent(
                    "verified",
                    {
                        "source": "text2sql",
                        "score": citations[0]["extra"]["score"] if citations else None,
                        "matched_question": data.get("intent_summary"),
                        "citations": citations,
                    },
                )
                async for ev in _finish(ctx, conv_id=conv_id, question=question,
                                        content=content, citations=citations, verified=True):
                    yield ev
                return
            elif outcome == "refused_out_of_template":
                # 问对了域、超出了已验收模板。**不交给生成模型** ——
                # 那只会换来一个听起来合理的编数,而这是问数链路最不能出的错
                content = data["reply"] or t2s.OUT_OF_TEMPLATE_REPLY
                parts.append(content)
                async for ev in _finish(ctx, conv_id=conv_id, question=question,
                                        content=content, citations=[], verified=False):
                    yield ev
                return
            # 🩸 refused_non_data:检索层零 LLM 就判掉了"这不是一个问数问题",
            # 本来就该由别的链路接手 —— 从 S2 起,接手的是**下面的文档 RAG**,
            # 而不是直接落到 generate 裸答(S2 集成时改,见 S2 分册 1 §4 Step 6)。

        # ---- stage: retrieve_doc_rag(S2)—— 串行兜底的最后一棒
        # 只在 Agent 绑了文档库时才跑。**没绑就一个事件都不发**:
        # 只绑了精准问答的 Agent,它的事件流与 S1 时代逐字相同,轨迹面板上不会多出空阶段。
        async with SessionLocal() as session:
            doc_kb_ids = await doc_rag.agent_document_kb_ids(session, agent_id)

        if doc_kb_ids:
            yield ChatEvent("stage_start", {"stage": STAGE_DOC_RAG})
            try:
                async with traced(ctx, STAGE_DOC_RAG, input={"question": question}) as span:
                    async with SessionLocal() as session:
                        hits, rag_trace = await doc_rag.retrieve(
                            session, question, kb_ids=doc_kb_ids
                        )
                    span.output = _doc_rag_trace(hits, rag_trace)
                if hits:
                    # 证据放在用户问题**之前**:模型先看到材料再看到问题,
                    # 而且历史对话不会把证据挤到上下文更远处
                    evidence = _doc_rag_context(hits)
                    prompt = [*prompt[:-1], evidence, prompt[-1]]
                    citations = _doc_rag_citations(hits)
                    # 校验要拿模型看到的那份材料逐字比对,所以留一份
                    doc_evidence = str(evidence["content"])
            except Exception as exc:
                # 与前两条链路同一条纪律:检索出错绝不能弄死一次问答,退化成"没召回"
                log.warning("chat_doc_rag_failed", agent_id=str(agent_id), error=str(exc))
                yield ChatEvent("error", {"stage": STAGE_DOC_RAG, "message": str(exc)})
            yield ChatEvent(
                "stage_end", {**spans_as_dicts(ctx.spans)[-1], "stage": STAGE_DOC_RAG}
            )

        yield ChatEvent("stage_start", {"stage": "generate"})
        try:
            async with traced(
                ctx,
                "generate",
                input={"question": question, "history_turns": len(history), "prompt": prompt},
            ) as span:
                async for ev in llm.stream(prompt, model_tier="main", temperature=temperature):
                    if ev.type == "token":
                        parts.append(ev.text)
                        yield ChatEvent("token", {"text": ev.text})
                    elif ev.result is not None:
                        final = ev.result
                        span.record_llm(ev.result)
                content = final.text if final else "".join(parts)
                span.output = {
                    "text": content,
                    "finish_reason": final.finish_reason if final else None,
                }
        except Exception as exc:
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            content = fallback
            log.warning("chat_generate_failed", agent_id=str(agent_id), error=error)
            yield ChatEvent("error", {"stage": "generate", "message": str(exc)})
            # 兜底话术也走 token 事件:前端只有一条渲染路径,不需要为失败写第二套
            yield ChatEvent("token", {"text": content})

        # stage_end 放在 try/except 之后而不是 finally 里:
        # 在 finally 里 yield,遇到客户端断开(GeneratorExit)会变成 RuntimeError
        span_dicts = spans_as_dicts(ctx.spans)
        yield ChatEvent("stage_end", {**span_dicts[-1], "stage": "generate"})

        # 兜底话术不是"根据证据回答"出来的,不能挂引用;
        # 正常答完则按正文筛出真正被引用的那几条(分册 3 §3b)
        answered = _doc_rag_used(content, citations) if status == "completed" else []

        # 一致性后校验(分册 3 §5-4):默认关。它只写进轨迹,**不改答案正文,也不动引用面板** ——
        # 一个诊断工具没资格改用户看到的结果,更不该因为自己出错就把问答判失败
        if settings.doc_rag_verify and answered and doc_evidence:
            # 🩸 **整块都在 try 里**:这一段跑在 `_persist` 之前,而外层只接住取消类异常 ——
            # 它抛出去,这次问答的助手消息与 trace 会一起没落库。
            # 一个默认关着的诊断开关没资格让用户丢掉一个已经答完的回答。
            # (实测踩过一次:verifier 里写错了一个字段名,答案就这么没了。)
            try:
                yield ChatEvent("stage_start", {"stage": STAGE_DOC_VERIFY})
                async with traced(ctx, STAGE_DOC_VERIFY, input={"answer": content}) as span:
                    report = await doc_verifier.verify(content, doc_evidence)
                    span.output = {"unsupported": [u.model_dump() for u in report.unsupported]}
                yield ChatEvent(
                    "stage_end", {**spans_as_dicts(ctx.spans)[-1], "stage": STAGE_DOC_VERIFY}
                )
            except (GeneratorExit, asyncio.CancelledError):
                raise
            except Exception as exc:
                log.warning("chat_doc_verify_failed", error=str(exc))

        await _persist(ctx, content=content, status=status, question=question,
                       citations=answered)

        yield ChatEvent(
            "done",
            {
                "message_id": str(ctx.message_id),
                "conversation_id": str(conv_id),
                "status": status,
                "usage": ctx.total_usage.as_dict(),
                "cost_usd": str(ctx.total_cost),
                "latency_ms": ctx.total_latency_ms,
                # 引用只能来自检索到的证据(文档 RAG 召回),生成的内容不许编引用
                "citations": answered,
                # 文档 RAG 的答案是模型写的,**不是**人工采纳过的原文 → 不标 Verified
                "verified": False,
                "trace": span_dicts,
                "error": error,
            },
        )
    except (GeneratorExit, asyncio.CancelledError):
        # 客户端中途断开(关页面 / 网络断)。此时本任务正在被取消,**不能再 await** ——
        # 落库交给一个 detach 出去的任务(它自己开 session)。不这么做的话 DB 里
        # 只剩一条用户提问、没有助手消息也没有 trace,演示时"中断了怎么办"没法回答。
        log.info("chat_interrupted", message_id=str(ctx.message_id), chars=len("".join(parts)))
        _detach(
            _persist(ctx, content="".join(parts), status="interrupted", question=question),
            name=f"persist-interrupted-{ctx.message_id}",
        )
        raise


async def run_chat(
    *,
    agent_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> ChatResult:
    """非流式入口:把 `chat_events()` 消费到底。评测执行器(S6)用的就是这个。"""
    parts: list[str] = []
    done: dict | None = None
    async for ev in chat_events(
        agent_id=agent_id,
        question=question,
        conversation_id=conversation_id,
        user_id=user_id,
    ):
        if ev.event == "token":
            parts.append(ev.data["text"])
        elif ev.event == "done":
            done = ev.data

    assert done is not None, "chat_events 必须以 done 事件结束"
    return ChatResult(
        message_id=uuid.UUID(done["message_id"]),
        conversation_id=uuid.UUID(done["conversation_id"]),
        # 成功是模型输出,失败是兜底话术 —— 两者都走 token 事件,所以这里一视同仁
        content="".join(parts),
        status=done["status"],
        usage=done["usage"],
        cost_usd=Decimal(done["cost_usd"]),
        latency_ms=done["latency_ms"],
        citations=done["citations"],
        verified=bool(done.get("verified")),
        trace=done["trace"],
    )
