"""结构化日志(structlog):每条日志带 request_id,dev 下彩色可读,prod 下 JSON。"""

import logging
import sys
from contextvars import ContextVar

import structlog

from app.config import settings

# 由中间件写入,日志处理器自动附加到每条日志上
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(_logger, _name, event_dict: dict) -> dict:
    rid = request_id_ctx.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    # uvicorn 的 access 日志太吵,交给我们自己的请求日志
    logging.getLogger("uvicorn.access").disabled = True

    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "dev"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
