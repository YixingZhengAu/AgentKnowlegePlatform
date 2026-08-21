"""FastAPI 应用工厂。

启动顺序:配置校验(import app.config 时已完成)-> 日志 -> 中间件 -> 异常处理 -> 路由。
生命周期里只做"轻"的事:建存储目录、探一次 DB;DB 不通只告警不阻止启动
(否则 /healthz 也起不来,反而看不到 unhealthy)。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.jobs import reap_abandoned_jobs
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware
from app.db import SessionLocal, engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        log.info("startup_db_ok", database=settings.database_url.rsplit("/", 1)[-1])
    except Exception as exc:
        # 起服务不因为数据库没起来而失败,/healthz 会如实报 unhealthy
        log.warning("startup_db_unavailable", error=str(exc))
    # 僵尸任务收尸:进程内 BackgroundTasks 不可能跨重启存活,
    # 所以启动这一刻还标着 running 的任务一定是上一条命的残留(Step 7 验收项)。
    try:
        reaped = await reap_abandoned_jobs()
        if reaped:
            log.warning("startup_jobs_reaped", count=reaped)
    except Exception as exc:
        log.warning("startup_reap_failed", error=str(exc))
    log.info(
        "startup",
        env=settings.app_env,
        llm_main=settings.llm_model_main,
        llm_light=settings.llm_model_light,
        embedding=f"{settings.embedding_model}({settings.embedding_dim})",
    )
    yield
    await engine.dispose()
    log.info("shutdown")


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title="Clenergy Knowledge Agent API",
        description="企业知识分层治理 + Agent 路由问答",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
