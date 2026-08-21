"""会话与消息 schema。"""

import uuid
from datetime import datetime

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
