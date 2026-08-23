"""路由汇总:所有子路由在这里挂到一个 APIRouter 上,main.py 只 include 一次。"""

from fastapi import APIRouter

from app.api import (
    agents,
    chat,
    conversations,
    exact_qa,
    files,
    health,
    jobs,
    kbs,
    staging,
    text2sql,
    traces,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(kbs.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(traces.router)
api_router.include_router(jobs.router)
api_router.include_router(staging.router)
# S1:精准问答的域接口 + 解析产物图片出口(M1.5)
api_router.include_router(exact_qa.router)
api_router.include_router(files.router)
# S3:智能问数的域接口(数据源 / Schema 治理 / 意图与模板 / 发布)
api_router.include_router(text2sql.router)

__all__ = ["api_router"]
