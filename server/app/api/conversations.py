"""会话只读接口(Step 7 对话页会在这上面加写接口)。"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.models import Conversation, Message
from app.schemas.common import ListResponse
from app.schemas.conversation import ConversationOut, MessageOut

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=ListResponse[ConversationOut])
async def list_conversations(session: SessionDep, user: CurrentUser) -> ListResponse:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.status == "active")
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    items = [ConversationOut.model_validate(r) for r in rows]
    return ListResponse[ConversationOut](items=items, total=len(items))


@router.get("/{conversation_id}/messages", response_model=ListResponse[MessageOut])
async def list_messages(conversation_id: uuid.UUID, session: SessionDep) -> ListResponse:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            )
        )
        .scalars()
        .all()
    )
    items = [MessageOut.model_validate(r) for r in rows]
    return ListResponse[MessageOut](items=items, total=len(items))
