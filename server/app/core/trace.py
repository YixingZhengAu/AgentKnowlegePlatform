"""Trace 框架:一次问答的分阶段执行记录。

S0 的技术核心之一。三条设计原则:

1. **失败也要落库**:异常阶段照样写一条 `status=error` 的 trace —— 失败记录比成功记录有价值。
2. **不阻塞主链路**:trace 先攒在内存 buffer(`ChatContext.spans`),问答结束一次性批量落库。
3. **只存摘要**:input/output 里的长文本统一截断(`TRUNCATE_AT`),trace 是给人看"发生了什么",
   不是给人看全文 —— 全文在 messages / chunks 表里。

用法:

```python
async with traced(ctx, "generate", input={"question": q}) as span:
    result = await llm.complete(...)
    span.output = {"text": result.text}
    span.record_llm(result)          # 一行带走 model / usage / cost
```
"""

import time
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Trace
from app.providers.base import LLMResult, TokenUsage

log = get_logger(__name__)

# 单个字符串字段落库前的截断长度
TRUNCATE_AT = 1000


def summarize(value: Any, *, limit: int = TRUNCATE_AT) -> Any:
    """递归截断:长字符串截断并标注原长度,容器逐项处理。"""
    if isinstance(value, str):
        if len(value) <= limit:
            return value
        return value[:limit] + f"…[truncated, total {len(value)} chars]"
    if isinstance(value, dict):
        return {k: summarize(v, limit=limit) for k, v in value.items()}
    if isinstance(value, list | tuple):
        # 列表最多留 20 项,再多也看不出问题
        items = [summarize(v, limit=limit) for v in list(value)[:20]]
        if len(value) > 20:
            items.append(f"…[{len(value) - 20} more]")
        return items
    if isinstance(value, Decimal):
        return str(value)
    return value


@dataclass(slots=True)
class TraceSpan:
    """一个阶段的可变记录。业务代码在 with 块里往上面填 output/usage。"""

    stage: str
    seq: int
    input: dict | None = None
    output: dict | None = None
    status: str = "ok"
    error: str | None = None
    latency_ms: int | None = None
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = None
    model: str | None = None

    def record_llm(self, result: LLMResult) -> None:
        """把一次 LLM 调用的计量信息一次性塞进 span。"""
        self.model = result.model
        self.usage = (self.usage + result.usage) if self.usage else result.usage
        self.cost_usd = (self.cost_usd or Decimal("0")) + result.cost_usd


@dataclass(slots=True)
class ChatContext:
    """一次问答的上下文:所有 stage 共享同一个 `message_id`(助手消息 id,预生成)。"""

    message_id: uuid.UUID
    agent_id: uuid.UUID
    conversation_id: uuid.UUID
    spans: list[TraceSpan] = field(default_factory=list)

    def next_seq(self) -> int:
        return len(self.spans) + 1

    @property
    def total_usage(self) -> TokenUsage:
        total = TokenUsage()
        for s in self.spans:
            if s.usage:
                total = total + s.usage
        return total

    @property
    def total_cost(self) -> Decimal:
        return sum((s.cost_usd or Decimal("0") for s in self.spans), Decimal("0"))

    @property
    def total_latency_ms(self) -> int:
        return sum(s.latency_ms or 0 for s in self.spans)


@asynccontextmanager
async def traced(
    ctx: ChatContext, stage: str, *, input: dict | None = None
) -> AsyncIterator[TraceSpan]:
    """给一个阶段计时并记账。异常会被记成 `status=error` 后原样抛出。"""
    span = TraceSpan(stage=stage, seq=ctx.next_seq(), input=input)
    ctx.spans.append(span)  # 先入列:异常路径也不会漏掉这条
    t0 = time.perf_counter()
    try:
        yield span
    except Exception as exc:
        span.status = "error"
        span.error = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        span.latency_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "trace_stage",
            stage=stage,
            seq=span.seq,
            status=span.status,
            latency_ms=span.latency_ms,
            model=span.model,
            tokens=span.usage.total_tokens if span.usage else 0,
        )


async def flush_traces(session: AsyncSession, ctx: ChatContext) -> int:
    """把 buffer 里的 span 批量写入 traces 表(调用方负责 commit)。

    注意:`traces.message_id` 外键指向 `messages.id`,**调用前助手消息必须已经落库**。
    """
    rows = [
        Trace(
            message_id=ctx.message_id,
            stage=s.stage,
            seq=s.seq,
            status=s.status,
            input=summarize(s.input) if s.input else None,
            output=summarize(s.output) if s.output else None,
            error=s.error,
            latency_ms=s.latency_ms,
            prompt_tokens=s.usage.prompt_tokens if s.usage else None,
            completion_tokens=s.usage.completion_tokens if s.usage else None,
            cost_usd=s.cost_usd,
            model=s.model,
        )
        for s in ctx.spans
    ]
    session.add_all(rows)
    return len(rows)


def spans_as_dicts(spans: Sequence[TraceSpan]) -> list[dict]:
    """给 SSE / 非流式返回体用的轻量表示(前端执行轨迹面板消费)。"""
    return [
        {
            "stage": s.stage,
            "seq": s.seq,
            "status": s.status,
            "latency_ms": s.latency_ms,
            "model": s.model,
            "usage": s.usage.as_dict() if s.usage else None,
            "cost_usd": str(s.cost_usd) if s.cost_usd is not None else None,
            "error": s.error,
        }
        for s in spans
    ]
