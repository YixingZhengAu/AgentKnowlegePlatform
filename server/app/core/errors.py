"""统一错误体与全局异常处理。

对外错误格式固定为 {"error": {"code", "message", "detail"}},
前端只需要认这一种结构(web/src/api/client.ts 依赖它)。
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx

log = get_logger(__name__)


class AppError(Exception):
    """业务异常基类:抛它就会被翻译成统一错误体。"""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(self, message: str, *, detail: Any = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ConfigError(AppError):
    """配置缺失/非法:启动期或首次调用外部服务时抛,报错要指名道姓缺哪个变量。"""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "config_error"


class ProviderError(AppError):
    """LLM / Embedding / Rerank 供应商调用失败(已重试后仍失败)。"""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"


def error_body(code: str, message: str, detail: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError):
        log.error("db_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_body("db_error", "Database is unavailable"),
        )

    @app.exception_handler(ConnectionError)
    async def _conn_error(_: Request, exc: ConnectionError):
        """连不上 Postgres 时 asyncpg 抛的是裸 ConnectionRefusedError,
        SQLAlchemy 不会包装它 —— 单独接住,别报成 internal_error。"""
        log.error("db_unreachable", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_body("db_error", "Database is unavailable"),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(
                "internal_error",
                "Internal server error",
                {"request_id": request_id_ctx.get()},
            ),
        )
