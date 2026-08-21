"""Agent 相关 schema。"""

import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class AgentKbBindingOut(ORMModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    kb_name: str
    kb_type: str
    priority: int
    enabled: bool
    top_k: int | None
    threshold: float | None
    usage_desc: str | None


class AgentOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    router_mode: str
    status: str
    created_at: datetime
    updated_at: datetime


class AgentDetailOut(AgentOut):
    system_prompt: str
    fallback_reply: str | None
    model_cfg: dict
    bindings: list[AgentKbBindingOut]
