"""路由依赖:DB session、当前用户(S0–S5 硬编码 default_user)。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConfigError
from app.db import get_session
from app.models import User
from app.models.user import DEFAULT_USERNAME

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(session: SessionDep) -> User:
    """S0–S5 没有用户体系:固定取 seed 出来的 default_user。"""
    user = (
        await session.execute(select(User).where(User.username == DEFAULT_USERNAME))
    ).scalar_one_or_none()
    if user is None:
        raise ConfigError(
            f"未找到默认用户 {DEFAULT_USERNAME},请先执行 `make seed`",
            code="seed_missing",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
