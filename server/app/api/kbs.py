"""知识库只读接口(Step 6 前端列表页的数据源)。"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import KnowledgeBase
from app.schemas.common import ListResponse
from app.schemas.knowledge import KnowledgeBaseOut

router = APIRouter(prefix="/api/kbs", tags=["kbs"])


@router.get("", response_model=ListResponse[KnowledgeBaseOut])
async def list_kbs(session: SessionDep, type: str | None = None) -> ListResponse:
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at)
    if type:
        stmt = stmt.where(KnowledgeBase.type == type)
    rows = (await session.execute(stmt)).scalars().all()
    items = [KnowledgeBaseOut.model_validate(r) for r in rows]
    return ListResponse[KnowledgeBaseOut](items=items, total=len(items))


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_kb(kb_id: uuid.UUID, session: SessionDep) -> KnowledgeBaseOut:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"Knowledge base {kb_id} not found")
    return KnowledgeBaseOut.model_validate(kb)
