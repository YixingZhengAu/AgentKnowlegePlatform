"""统一重试与错误翻译:所有供应商调用都过这里。

分三类处理,原则是"能重试的重试,不能重试的立刻说清原因":
- 瞬时故障(限流 / 超时 / 连接 / 5xx):指数退避 + 抖动重试
- 鉴权失败:立刻抛 `ConfigError`,提示去检查 .env 的 key(这是配置问题,不是"服务不可用")
- 其余供应商错误:抛 `ProviderError`(502)
"""

import asyncio
import random
from collections.abc import Awaitable, Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.errors import ConfigError, ProviderError
from app.core.logging import get_logger

log = get_logger(__name__)

RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


def translate_error(exc: Exception, *, op: str) -> Exception:
    """把供应商 SDK 的异常翻译成本项目的统一异常类型。"""
    if isinstance(exc, AuthenticationError | PermissionDeniedError):
        return ConfigError(
            "LLM 供应商拒绝了凭据。请检查仓库根 .env 里的 OPENAI_API_KEY 是否有效、是否有权限。",
            code="provider_auth_error",
            detail={"op": op, "provider_message": str(exc)},
        )
    if isinstance(exc, APIStatusError):
        return ProviderError(
            f"Provider call failed ({op}): HTTP {exc.status_code}",
            detail={"op": op, "status": exc.status_code, "provider_message": str(exc)},
        )
    if isinstance(exc, OpenAIError):
        return ProviderError(
            f"Provider call failed ({op}): {type(exc).__name__}",
            detail={"op": op, "provider_message": str(exc)},
        )
    return exc


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    op: str,
    attempts: int,
    base_delay: float = 0.5,
) -> T:
    """重试 `fn`(无参协程工厂)。最后一次仍失败就抛翻译后的异常。"""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return await fn()
        except RETRYABLE as exc:
            last = exc
            if i == attempts:
                break
            # 指数退避 + 抖动:并发多请求同时被限流时避免同步重试雪崩
            delay = base_delay * (2 ** (i - 1)) * (1 + random.random() * 0.3)
            log.warning(
                "provider_retry",
                op=op,
                attempt=i,
                max_attempts=attempts,
                delay_sec=round(delay, 2),
                error=type(exc).__name__,
            )
            await asyncio.sleep(delay)
        except Exception as exc:  # 不可重试:立刻翻译上抛
            raise translate_error(exc, op=op) from exc

    assert last is not None
    log.error("provider_failed", op=op, attempts=attempts, error=type(last).__name__)
    raise translate_error(last, op=op) from last
