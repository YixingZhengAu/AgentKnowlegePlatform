"""Trace 框架的离线测试(不碰 DB):计时、异常记录、摘要截断、汇总。"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.trace import TRUNCATE_AT, ChatContext, spans_as_dicts, summarize, traced
from app.providers.base import LLMResult, TokenUsage


def _ctx() -> ChatContext:
    return ChatContext(message_id=uuid4(), agent_id=uuid4(), conversation_id=uuid4())


async def test_traced_records_ok_and_usage():
    ctx = _ctx()
    async with traced(ctx, "generate", input={"q": "hi"}) as span:
        span.output = {"text": "ok"}
        span.record_llm(
            LLMResult(text="ok", model="gpt-5", usage=TokenUsage(10, 20), cost_usd=Decimal("0.5"))
        )
    (s,) = ctx.spans
    assert (s.stage, s.seq, s.status) == ("generate", 1, "ok")
    assert s.latency_ms is not None and s.latency_ms >= 0
    assert s.model == "gpt-5" and s.usage == TokenUsage(10, 20)
    assert ctx.total_cost == Decimal("0.5")
    assert ctx.total_usage.total_tokens == 30


async def test_traced_records_error_and_reraises():
    ctx = _ctx()
    with pytest.raises(RuntimeError):
        async with traced(ctx, "retrieve"):
            raise RuntimeError("boom")
    # 失败的 trace 也必须留在 buffer 里 —— 它比成功的更有价值
    (s,) = ctx.spans
    assert s.status == "error"
    assert "RuntimeError: boom" in s.error
    assert s.latency_ms is not None


async def test_seq_increments_across_stages():
    ctx = _ctx()
    for stage in ("route", "retrieve", "generate"):
        async with traced(ctx, stage):
            pass
    assert [s.seq for s in ctx.spans] == [1, 2, 3]
    assert [d["stage"] for d in spans_as_dicts(ctx.spans)] == ["route", "retrieve", "generate"]


def test_summarize_truncates_long_strings():
    out = summarize({"text": "x" * (TRUNCATE_AT + 50)})
    assert out["text"].startswith("x" * 10)
    assert "truncated" in out["text"]
    assert len(out["text"]) < TRUNCATE_AT + 60


def test_summarize_caps_lists_and_recurses():
    out = summarize({"prompt": [{"content": "y" * 2000}] * 25})
    assert len(out["prompt"]) == 21  # 20 项 + 一条 "…[5 more]"
    assert "more" in out["prompt"][-1]
    assert "truncated" in out["prompt"][0]["content"]


def test_summarize_stringifies_decimal():
    assert summarize({"cost": Decimal("0.001")}) == {"cost": "0.001"}
