"""knowledge_bases:三类知识库的登记表(类型建库后不可改)。"""

import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_check

KB_TYPES = ("exact_qa", "document", "text2sql")
KB_STATUSES = ("active", "archived")


class KnowledgeBase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        enum_check("type", KB_TYPES, "ck_knowledge_bases_type"),
        enum_check("status", KB_STATUSES, "ck_knowledge_bases_status"),
        Index("ix_knowledge_bases_owner_id", "owner_id"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # 也会喂给 S4 路由 LLM 作为"这个库适合回答什么"的参考
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
