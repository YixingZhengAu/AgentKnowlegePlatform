"""路由汇总:所有子路由在这里挂到一个 APIRouter 上,main.py 只 include 一次。"""

from fastapi import APIRouter

from app.api import agents, conversations, health, kbs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(kbs.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)

__all__ = ["api_router"]
