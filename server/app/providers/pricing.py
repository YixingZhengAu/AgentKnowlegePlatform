"""模型价格表:把 token 用量折成美元,给 trace / 前端"成本"列用。

为什么写死在代码里而不是配置:价格是"事实"不是"环境",改价格属于改代码(要 review)。
未知型号返回 0 并告警一次 —— 宁可成本显示 0,不能因为价格表没更新就让问答链路挂掉。
"""

from decimal import ROUND_HALF_UP, Decimal

from app.core.logging import get_logger
from app.providers.base import TokenUsage

log = get_logger(__name__)

# 单位:美元 / 1M tokens。(input, output);embedding 只有 input
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-5": (Decimal("1.25"), Decimal("10.00")),
    "gpt-5-mini": (Decimal("0.25"), Decimal("2.00")),
    "gpt-5-nano": (Decimal("0.05"), Decimal("0.40")),
    "gpt-4.1": (Decimal("2.00"), Decimal("8.00")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60")),
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0")),
    "text-embedding-3-large": (Decimal("0.13"), Decimal("0")),
}

_MILLION = Decimal("1000000")
_QUANT = Decimal("0.000001")  # 对齐 traces.cost_usd 的 numeric(10,6)
_warned: set[str] = set()


def _lookup(model: str) -> tuple[Decimal, Decimal] | None:
    if model in PRICES:
        return PRICES[model]
    # 带日期后缀的快照名(gpt-5-2026-01-01)按前缀匹配,取最长匹配
    matches = [k for k in PRICES if model.startswith(k)]
    if matches:
        return PRICES[max(matches, key=len)]
    return None


def estimate_cost(model: str, usage: TokenUsage) -> Decimal:
    price = _lookup(model)
    if price is None:
        if model not in _warned:
            _warned.add(model)
            log.warning("pricing_unknown_model", model=model, hint="在 providers/pricing.py 补价格")
        return Decimal("0")
    inp, out = price
    total = (Decimal(usage.prompt_tokens) * inp + Decimal(usage.completion_tokens) * out) / _MILLION
    return total.quantize(_QUANT, rounding=ROUND_HALF_UP)
