"""Provider 层的离线测试:不打真实 API,只验"接口形状与本地逻辑"。

真实调用的验证在 `scripts/smoke_llm.py` / `scripts/smoke_embedding.py`(要花钱、要网络),
所以 CI 能跑的这部分只覆盖:Protocol 一致性、价格换算、透传 rerank、JSON 轻量校验。
"""

from decimal import Decimal

import pytest

from app.providers import (
    EmbeddingProvider,
    LLMProvider,
    RerankProvider,
    TokenUsage,
    get_embedder,
    get_llm,
    get_reranker,
)
from app.providers.openai_llm import _response_format, _validate_json
from app.providers.pricing import estimate_cost


def test_registry_returns_protocol_conforming_impls():
    assert isinstance(get_llm(), LLMProvider)
    assert isinstance(get_embedder(), EmbeddingProvider)
    assert isinstance(get_reranker(), RerankProvider)


def test_registry_is_singleton():
    # 客户端里有连接池,重复 new 会浪费连接
    assert get_llm() is get_llm()


def test_embedder_dim_follows_config():
    from app.config import settings

    assert get_embedder().dim == settings.embedding_dim


def test_token_usage_add():
    u = TokenUsage(10, 5) + TokenUsage(1, 2)
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (11, 7, 18)


def test_pricing_known_model():
    # gpt-5: $1.25 / 1M in, $10 / 1M out
    cost = estimate_cost("gpt-5", TokenUsage(prompt_tokens=1_000_000, completion_tokens=100_000))
    assert cost == Decimal("2.250000")


def test_pricing_date_suffixed_snapshot_matches_prefix():
    assert estimate_cost("gpt-5-mini-2026-01-01", TokenUsage(1_000_000, 0)) == Decimal("0.250000")


def test_pricing_unknown_model_is_zero_not_crash():
    assert estimate_cost("some-future-model", TokenUsage(1000, 1000)) == Decimal("0")


def test_validate_json_accepts_and_rejects():
    schema = {"schema": {"type": "object", "required": ["targets"]}}
    assert _validate_json('{"targets": ["exact_qa"]}', schema) == {"targets": ["exact_qa"]}
    with pytest.raises(ValueError, match="缺少必填字段"):
        _validate_json('{"reason": "x"}', schema)
    with pytest.raises(ValueError, match="顶层必须是对象"):
        _validate_json("[1,2]", schema)


def test_response_format_accepts_both_shapes():
    wrapped = _response_format({"name": "route", "schema": {"type": "object"}})
    assert wrapped["json_schema"]["name"] == "route"
    bare = _response_format({"type": "object"})
    assert bare["json_schema"]["name"] == "result"
    assert bare["json_schema"]["schema"] == {"type": "object"}


async def test_passthrough_rerank_keeps_order_and_truncates():
    hits = await get_reranker().rerank("q", ["a", "b", "c"], top_n=2)
    assert [h.index for h in hits] == [0, 1]
    assert [h.document for h in hits] == ["a", "b"]
    assert hits[0].score > hits[1].score  # 单调递减,形状与真实 reranker 一致
