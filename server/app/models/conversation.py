"""会话域:conversations / messages / message_citations。

messages.route_decision 存 S4 路由结果快照;citations 是"强制引用"的落地。
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

CONVERSATION_STATUSES = ("active", "archived")
MESSAGE_ROLES = ("user", "assistant")
MESSAGE_STATUSES = ("completed", "failed", "interrupted")
CITATION_TYPES = ("exact_qa", "chunk", "sql")


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        enum_check("status", CONVERSATION_STATUSES, "ck_conversations_status"),
        Index("ix_conversations_user_last_message", "user_id", "last_message_at"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 首问自动截断生成
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    last_message_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        enum_check("role", MESSAGE_ROLES, "ck_messages_role"),
        enum_check("status", MESSAGE_STATUSES, "ck_messages_status"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="completed")
    # S4 路由结果快照:{"targets":["exact_qa"],"reason":"..."}
    route_decision: Mapped[dict | None] = mapped_column(JSONB)
    # 汇总 token / 成本
    usage: Mapped[dict | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class MessageCitation(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint("message_id", "seq", name="uq_message_citations_seq"),
        enum_check("citation_type", CITATION_TYPES, "ck_message_citations_type"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    # 正文中 [1][2] 的编号
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_type: Mapped[str] = mapped_column(Text, nullable=False)
    # 指向 exact_qa_items.id / chunks.id;sql 类型为 NULL(弱引用,不建 FK)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    snippet: Mapped[str | None] = mapped_column(Text)
    # 相似度分数 / SQL 文本 / 结果行数等
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
