"""执行轨迹查询:一次问答的全部 stage(Step 7 前端右侧面板的数据源)。"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import Message, Trace
from app.schemas.chat import TraceOut
from app.schemas.common import ListResponse

router = APIRouter(prefix="/api/traces", tags=["observability"])


@router.get("/{message_id}", response_model=ListResponse[TraceOut])
async def get_traces(message_id: uuid.UUID, session: SessionDep) -> ListResponse:
    # 消息不存在与"消息存在但没有 trace"是两件事,前者报 404
    if await session.get(Message, message_id) is None:
        raise NotFoundError(f"Message {message_id} not found")
    rows = (
        (
            await session.execute(
                select(Trace).where(Trace.message_id == message_id).order_by(Trace.seq)
            )
        )
        .scalars()
        .all()
    )
    items = [TraceOut.model_validate(r) for r in rows]
    return ListResponse[TraceOut](items=items, total=len(items))
