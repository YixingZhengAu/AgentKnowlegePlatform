"""`run_chat()` —— 问答的唯一入口(D4:HTTP / SSE / 评测执行器共用一条链路)。

**单入口是怎么做到的**:真正的编排只有一个 async generator `chat_events()`,它永远产出事件流;
非流式的 `run_chat()` 只是把这个事件流消费到底再拼成 `ChatResult`。
所以"流式"和"非流式"不是两份代码 —— S1–S4 往编排里插阶段,两条路径同时生效,不可能只改到一边。

S0 版本的链路刻意简单:

    加载 agent → 存用户消息 → [stage: generate] 调 LLM → 存回复 → flush traces

**没有检索、没有路由**。但"形状"现在就定死了:stage 序列 + 事件协议 + trace 落库时机。
S1 插 `retrieve_exact_qa`、S4 插 `route`,都是往这里加一个 `async with traced(...)` 块,
事件协议一个字不用改。
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.core.trace import ChatContext, flush_traces, spans_as_dicts, traced
from app.db import SessionLocal
from app.models import Agent, Conversation, Message, User
from app.models.user import DEFAULT_USERNAME
from app.providers import ChatMessage, get_llm

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


async def _persist(ctx: ChatContext, *, content: str, status: str, question: str) -> None:
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
        **usage.as_dict(),
        cost_usd=str(ctx.total_cost),
    )


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

    try:
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

        await _persist(ctx, content=content, status=status, question=question)

        yield ChatEvent(
            "done",
            {
                "message_id": str(ctx.message_id),
                "conversation_id": str(conv_id),
                "status": status,
                "usage": ctx.total_usage.as_dict(),
                "cost_usd": str(ctx.total_cost),
                "latency_ms": ctx.total_latency_ms,
                # S1/S2 起这里会有内容;S0 固定为空(没有检索就不该有引用)
                "citations": [],
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
        trace=done["trace"],
    )
