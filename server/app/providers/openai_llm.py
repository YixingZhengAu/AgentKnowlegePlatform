"""OpenAI LLM 实现(Chat Completions)。

三个值得讲的处理:
1. **tier 而非型号**:入参只有 `model_tier`,型号由 `settings.model_for_tier()` 给。
2. **JSON 模式自愈**:`json_schema` 走 structured output;万一仍拿不到合法 JSON,
   带着报错把上一轮回复喂回去重试(共 3 次),usage 累加,`attempts` 记在结果里。
3. **参数能力回退**:推理型模型不接受 `temperature` 之类参数。第一次被拒后记住
   "这个型号不支持这个参数",去掉重发,并对该进程后续调用直接不再带 —— 换型号不用改业务代码。
"""

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

from openai import AsyncOpenAI, BadRequestError

from app.config import Settings
from app.config import settings as default_settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.base import (
    ChatMessage,
    LLMResult,
    ModelTier,
    StreamEvent,
    TokenUsage,
)
from app.providers.pricing import estimate_cost
from app.providers.retry import with_retry

log = get_logger(__name__)

# 进程级记忆:{(型号, 参数名)} 已确认不被支持,后续调用直接不带
_UNSUPPORTED: set[tuple[str, str]] = set()
# 可以被"去掉重发"的参数(去掉它们只影响效果,不影响语义)
_DROPPABLE = ("temperature", "reasoning_effort")

# 推理型模型:reasoning token 与回答共用 max_completion_tokens 预算,必须额外留出 headroom
_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _is_reasoning(model: str) -> bool:
    return model.startswith(_REASONING_PREFIXES)

JSON_MAX_ATTEMPTS = 3  # 首次 + 2 次校验失败重试(S0-PLAN Step 4)


def _unsupported_param(exc: BadRequestError) -> str | None:
    """从 400 报错里问出"是哪个参数不行"。SDK 的 body 里通常直接给 param。"""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") or {}
        param = err.get("param")
        if isinstance(param, str) and param in _DROPPABLE:
            return param
    msg = str(exc)
    return next((p for p in _DROPPABLE if f"'{p}'" in msg), None)


def _usage_of(raw: Any) -> TokenUsage:
    u = getattr(raw, "usage", None)
    if u is None:
        return TokenUsage()
    return TokenUsage(
        prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(u, "completion_tokens", 0) or 0,
    )


def _response_format(json_schema: dict[str, Any]) -> dict[str, Any]:
    """接受两种写法:{"name":..., "schema":...} 或直接一个 JSON Schema。"""
    if "schema" in json_schema:
        name = json_schema.get("name", "result")
        schema = json_schema["schema"]
    else:
        name, schema = "result", json_schema
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "schema": schema, "strict": False},
    }


def _validate_json(text: str, schema: dict[str, Any]) -> dict:
    """轻量校验:能解析成对象 + 顶层 required 字段齐全。

    刻意不引 jsonschema 依赖 —— 我们只需要"够不够用来跑下一步",
    真正的字段级校验交给调用方的 Pydantic 模型(schemas/)。
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")
    inner = schema.get("schema", schema)
    missing = [k for k in inner.get("required", []) if k not in data]
    if missing:
        raise ValueError(f"缺少必填字段: {', '.join(missing)}")
    return data


def _guard_empty(text: str, finish_reason: str | None, model: str, payload: dict) -> None:
    """空回复不能静默返回。

    最常见的原因是推理型模型把 max_completion_tokens 全花在思考上(finish_reason=length,
    content 为空)。这种情况报错要直接说清怎么修,而不是让上层拿着空串继续跑。
    """
    if text.strip():
        return
    if finish_reason == "length":
        raise ProviderError(
            f"{model} 的 token 预算被推理耗尽,没有产出回答。"
            "请调大 max_tokens 或 LLM_REASONING_HEADROOM,或把 LLM_REASONING_EFFORT 降到 minimal。",
            detail={
                "finish_reason": finish_reason,
                "max_completion_tokens": payload.get("max_completion_tokens"),
                "reasoning_effort": payload.get("reasoning_effort"),
            },
        )
    raise ProviderError(
        f"{model} 返回了空回复", detail={"finish_reason": finish_reason}
    )


class OpenAILLMProvider:
    """LLMProvider 的 OpenAI 实现。"""

    def __init__(self, settings: Settings | None = None):
        self._s = settings or default_settings
        # max_retries=0:重试由我们自己做,日志/退避/异常翻译才能统一
        self._client = AsyncOpenAI(
            api_key=self._s.openai_api_key,
            base_url=self._s.openai_base_url,
            timeout=self._s.llm_timeout_sec,
            max_retries=0,
        )

    # ---------- 内部 ----------

    async def _create(self, **kwargs: Any) -> Any:
        model = kwargs["model"]
        for p in _DROPPABLE:
            if (model, p) in _UNSUPPORTED:
                kwargs.pop(p, None)
        try:
            return await self._client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            param = _unsupported_param(exc)
            if param and param in kwargs:
                _UNSUPPORTED.add((model, param))
                kwargs.pop(param)
                log.warning("provider_param_unsupported", model=model, param=param)
                return await self._client.chat.completions.create(**kwargs)
            raise

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        tier: ModelTier,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        model = self._s.model_for_tier(tier)
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            # 新型号只认 max_completion_tokens(max_tokens 已废弃)
            "max_completion_tokens": max_tokens,
        }
        if _is_reasoning(model):
            # max_tokens 语义保持为"回答预算";思考预算额外加,否则思考吃满就返回空字符串
            payload["max_completion_tokens"] = max_tokens + self._s.llm_reasoning_headroom
            payload["reasoning_effort"] = self._s.llm_reasoning_effort
            # 推理模型普遍不接受 temperature,先不带(被拒一次才发现太慢)
            payload.pop("temperature")
        return payload

    # ---------- 对外 ----------

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_tier: ModelTier = "main",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResult:
        payload = self._payload(messages, model_tier, temperature, max_tokens)
        model = payload["model"]
        if json_schema:
            payload["response_format"] = _response_format(json_schema)

        convo: list[ChatMessage] = list(payload["messages"])
        usage_total = TokenUsage()
        max_attempts = JSON_MAX_ATTEMPTS if json_schema else 1
        t0 = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            payload["messages"] = convo
            raw = await with_retry(
                lambda: self._create(**payload),
                op=f"llm.complete[{model}]",
                attempts=self._s.provider_max_attempts,
            )
            choice = raw.choices[0]
            text = choice.message.content or ""
            usage_total = usage_total + _usage_of(raw)
            _guard_empty(text, choice.finish_reason, model, payload)

            if not json_schema:
                log.info(
                    "llm_complete",
                    model=model,
                    tier=model_tier,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    **usage_total.as_dict(),
                )
                return LLMResult(
                    text=text,
                    model=model,
                    usage=usage_total,
                    cost_usd=estimate_cost(model, usage_total),
                    finish_reason=choice.finish_reason,
                )

            try:
                data = _validate_json(text, json_schema)
            except (json.JSONDecodeError, ValueError) as exc:
                log.warning("llm_json_invalid", model=model, attempt=attempt, error=str(exc))
                if attempt == max_attempts:
                    raise ProviderError(
                        "LLM 连续返回不合法的 JSON",
                        detail={"attempts": attempt, "last_error": str(exc), "raw": text[:500]},
                    ) from exc
                # 把错误喂回去,让模型自己改(比重发同样的 prompt 有效得多)
                convo = [
                    *convo,
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": (
                            f"Your reply was invalid JSON: {exc}. Reply with valid JSON only."
                        ),
                    },
                ]
                continue

            log.info(
                "llm_complete_json",
                model=model,
                tier=model_tier,
                attempts=attempt,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                **usage_total.as_dict(),
            )
            return LLMResult(
                text=text,
                model=model,
                usage=usage_total,
                cost_usd=estimate_cost(model, usage_total),
                finish_reason=choice.finish_reason,
                data=data,
                attempts=attempt,
            )

        raise AssertionError("unreachable")  # pragma: no cover

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_tier: ModelTier = "main",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamEvent]:
        payload = self._payload(messages, model_tier, temperature, max_tokens)
        model = payload["model"]
        # include_usage:最后一个空 chunk 才带 usage,不要它就统计不到 token
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        t0 = time.perf_counter()
        # 建流本身可重试;流中途断了不重试(已经吐出去的 token 收不回来)
        stream = await with_retry(
            lambda: self._create(**payload),
            op=f"llm.stream[{model}]",
            attempts=self._s.provider_max_attempts,
        )

        parts: list[str] = []
        usage = TokenUsage()
        finish_reason: str | None = None
        try:
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = _usage_of(chunk)
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta.content if choice.delta else None
                if delta:
                    parts.append(delta)
                    yield StreamEvent(type="token", text=delta)
        except Exception as exc:
            from app.providers.retry import translate_error

            raise translate_error(exc, op=f"llm.stream[{model}]") from exc

        text = "".join(parts)
        log.info(
            "llm_stream",
            model=model,
            tier=model_tier,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            **usage.as_dict(),
        )
        yield StreamEvent(
            type="end",
            result=LLMResult(
                text=text,
                model=model,
                usage=usage,
                cost_usd=estimate_cost(model, usage),
                finish_reason=finish_reason,
            ),
        )
