"""LLM 调用适配层:把 Phase B 的 `complete(messages, tier=..., json_schema=...)` 调用形状
接到正式的 `app/providers` 上。

★ 为什么要这一层而不是直接改各模块的调用点:Phase B 的六个生成环节(description / 意图 /
  模板 / 参数预填 / 相似问法 / 运行时改写)全部按这个形状写的 prompt 与回灌重试逻辑,
  是**评审过的代码**。让调用形状保持不变,迁移就只剩"换执行者",不掺杂改写。

实验床与正式 provider 的行为是逐项对齐的(所以迁移不改准确率):
  * tier→型号映射只来自 `.env` 的 LLM_MODEL_MAIN/LIGHT,业务代码不写型号名;
  * gpt-5 系:`max_completion_tokens = max_tokens + LLM_REASONING_HEADROOM`、
    带 `reasoning_effort`、不带 temperature;
  * json_schema 走 structured output(`strict: False`),拿不到合法 JSON 时带着报错
    回灌重试(共 3 次)。这三条正式 provider 里都已经实现,不用再包一层。

唯一的差异是**加了记账**:`LLMResult` 带 usage/cost。但 Phase B 的调用行只接收 dict ——
改它们的签名就等于改评审过的代码。所以记账走 `collect_usage()`:一个 contextvar 的收集桶,
调用方在外面开一个 with,桶里就有这段代码里发生的每一次调用的 `LLMResult`。
运行时链路(`core/chat.py` 的问数 stage)靠它把改写模型的账记进 trace,
否则这条链路在成本面板上是个黑洞。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers import LLMResult, ModelTier, get_llm

log = get_logger(__name__)

#: 当前 with 块的记账桶。None = 没人收(生成期的 Job 就不收,它们的账走 Job 自己的记录)
_COLLECTOR: ContextVar[list[LLMResult] | None] = ContextVar("text2sql_llm_results", default=None)


@contextmanager
def collect_usage() -> Iterator[list[LLMResult]]:
    """收集这段代码里发生的每次 LLM 调用的 `LLMResult`(给 trace 记账)。

    用 contextvar 而不是给 `complete()` 加返回值:后者会改掉六个评审过的模块的调用行。
    嵌套安全(reset 用 token),并发安全(每个 task 各有一份)。
    """
    bucket: list[LLMResult] = []
    token = _COLLECTOR.set(bucket)
    try:
        yield bucket
    finally:
        _COLLECTOR.reset(token)


def _record(result: LLMResult) -> None:
    bucket = _COLLECTOR.get()
    if bucket is not None:
        bucket.append(result)


async def complete_json(
    messages: list[dict[str, str]],
    *,
    tier: ModelTier = "main",
    max_tokens: int = 2048,
    json_schema: dict[str, Any],
    tag: str = "call",
) -> tuple[dict, LLMResult]:
    """结构化输出调用。返回 (解析好的 dict, LLMResult)。

    `tag` 只进日志:六个生成环节共用一条链路,出问题时要能一眼看出是哪一环。
    """
    result = await get_llm().complete(
        messages,  # type: ignore[arg-type]
        model_tier=tier,
        max_tokens=max_tokens,
        json_schema=json_schema,
    )
    if result.data is None:
        raise ProviderError(
            f"{tag}: the model did not return parseable JSON",
            detail={"raw": result.text[:500]},
            code="structured_output_missing",
        )
    log.info("text2sql_llm_call", tag=tag, tier=tier, attempts=result.attempts,
             tokens=result.usage.total_tokens)
    _record(result)
    return result.data, result


async def complete(
    messages: list[dict[str, str]],
    *,
    tier: ModelTier = "main",
    max_tokens: int = 2048,
    json_schema: dict[str, Any] | None = None,
    tag: str = "call",
) -> dict | str:
    """与实验床同形的入口:有 json_schema 返回 dict,否则返回文本。

    Phase B 的模块都调它,所以那些文件里的调用行一个字都不用改。
    """
    if json_schema is not None:
        data, _ = await complete_json(messages, tier=tier, max_tokens=max_tokens,
                                      json_schema=json_schema, tag=tag)
        return data
    result = await get_llm().complete(
        messages, model_tier=tier, max_tokens=max_tokens)  # type: ignore[arg-type]
    _record(result)
    return result.text
