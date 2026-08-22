"""会话与消息 schema。"""

import uuid
from datetime import datetime

from app.schemas.chat import MessageCitationOut
from app.schemas.common import ORMModel


class ConversationOut(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    status: str
    last_message_at: datetime | None
    created_at: datetime


class MessageOut(ORMModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    route_decision: dict | None
    usage: dict | None
    latency_ms: int | None
    created_at: datetime
    #: 历史消息也要带引用 —— 否则刷新一次页面,"凭什么可信"就没了
    citations: list[MessageCitationOut] = []
    #: true = 这条答案是人工采纳过的标准答案原样返回(由 exact_qa 引用判定,规则只在后端一处)
    verified: bool = False
