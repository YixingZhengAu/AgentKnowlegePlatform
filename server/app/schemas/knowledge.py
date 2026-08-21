"""知识库相关 schema。"""

import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class KnowledgeBaseOut(ORMModel):
    id: uuid.UUID
    name: str
    type: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
