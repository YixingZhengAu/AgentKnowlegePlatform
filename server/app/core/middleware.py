"""请求中间件:给每个请求分配 request_id,记一条结构化访问日志。"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, request_id_ctx

log = get_logger("http")
REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = rid
        # /healthz 每秒可能被探活,降噪
        if request.url.path != "/healthz":
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=elapsed_ms,
            )
        request_id_ctx.reset(token)
        return response
