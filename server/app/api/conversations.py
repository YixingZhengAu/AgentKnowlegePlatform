"""会话接口:列表 / 消息 / 删除。

**为什么没有"新建会话"接口**:`chat` 接口不传 `conversation_id` 就等于新开一轮
(见 `app/core/chat.py`)。前端点"New chat"只是把当前会话置空,不需要先请求一次 ——
少一次往返,也少一种"建了会话却没发消息"的空数据。

删除是**软删**(status=archived):对话与 trace 是演示时要复盘的证据,不真删。
"""

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.models import Conversation, Message, MessageCitation
from app.schemas.chat import MessageCitationOut
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
    # 引用一次查完再按消息分组 —— 每条消息各查一次就是 N+1,消息多了一眼可见
    cites: dict[uuid.UUID, list[MessageCitation]] = {}
    if rows:
        cite_rows = (
            (
                await session.execute(
                    select(MessageCitation)
                    .where(MessageCitation.message_id.in_([m.id for m in rows]))
                    .order_by(MessageCitation.seq)
                )
            )
            .scalars()
            .all()
        )
        for c in cite_rows:
            cites.setdefault(c.message_id, []).append(c)

    items = []
    for r in rows:
        out = MessageOut.model_validate(r)
        out.citations = [MessageCitationOut.model_validate(c) for c in cites.get(r.id, [])]
        # verified 的判定规则只写在后端这一处:有 exact_qa 引用 = 答案是采纳过的标准答案原样返回
        out.verified = any(c.citation_type == "exact_qa" for c in out.citations)
        items.append(out)
    return ListResponse[MessageOut](items=items, total=len(items))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: uuid.UUID, session: SessionDep) -> None:
    """软删:置 archived 就从列表里消失了,消息与 trace 都留着。"""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")
    conv.status = "archived"
    await session.commit()
