"""一致性后校验的**失败纪律**(分册 3 §5-4)。

为什么单独钉住:这一步跑在 `_persist` 之前,而它是个默认关着的诊断开关 ——
它抛异常就会把一次**已经答完**的问答连消息带 trace 一起弄丢。
2026-08-25 实测踩过一次(verifier 里写错了 `LLMResult` 的字段名),所以这里
只测一件事:**不管里面出什么事,verify() 都得安静地返回空报告。**
"""

import pytest

from app.core.errors import ProviderError
from app.services.document import verifier


@pytest.mark.asyncio
async def test_provider_error_degrades_to_empty_report(monkeypatch):
    """模型调用炸了 → 空报告,不抛。"""

    async def boom(*args, **kwargs):
        raise ProviderError("upstream is down", code="provider_unavailable")

    monkeypatch.setattr(verifier, "parse_structured", boom)
    assert (await verifier.verify("some answer", "some evidence")).unsupported == []


@pytest.mark.asyncio
async def test_any_exception_degrades_to_empty_report(monkeypatch):
    """连字段名写错这种**自己人的 bug** 也不许漏出去 —— 就是当初丢答案的那一下。"""

    async def boom(*args, **kwargs):
        raise AttributeError("'LLMResult' object has no attribute 'cost'")

    monkeypatch.setattr(verifier, "parse_structured", boom)
    assert (await verifier.verify("some answer", "some evidence")).unsupported == []


@pytest.mark.asyncio
async def test_report_passes_through(monkeypatch):
    """正常路径:模型判出来的东西原样返回。"""
    report = verifier.VerifyReport(
        unsupported=[verifier.UnsupportedClaim(claim="It ships in 2 days.", reason="Not stated.")]
    )

    async def ok(*args, **kwargs):
        return report, _FakeResult()

    monkeypatch.setattr(verifier, "parse_structured", ok)
    out = await verifier.verify("It ships in 2 days.", "evidence")
    assert [u.claim for u in out.unsupported] == ["It ships in 2 days."]


class _FakeResult:
    """只提供 verify() 记账要用的那个字段。"""

    cost_usd = 0
