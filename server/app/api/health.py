"""健康检查:含 DB 连通性。DB 挂了要返回 unhealthy 而不是崩溃。"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.config import settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])
log = get_logger(__name__)


@router.get("/healthz", response_model=HealthResponse)
async def healthz(response: Response) -> HealthResponse:
    db_ok = True
    db_error: str | None = None
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # DB 不可用不能让探活接口 500
        db_ok = False
        db_error = type(exc).__name__
        log.warning("healthz_db_unavailable", error=str(exc))

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if db_ok else "unhealthy",
        env=settings.app_env,
        database="ok" if db_ok else "unavailable",
        database_error=db_error,
        embedding_dim=settings.embedding_dim,
    )
