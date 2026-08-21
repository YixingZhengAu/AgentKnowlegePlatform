"""观测域:traces(每次问答的分阶段执行记录)+ feedbacks + unanswered_pool。

traces 是 S0 的技术核心之一:失败的 trace 也落库,失败记录比成功记录更有价值。
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

TRACE_STATUSES = ("ok", "error")
FEEDBACK_VOTES = ("up", "down")
FEEDBACK_REASONS = ("wrong", "incomplete", "irrelevant", "other")
UNANSWERED_REASONS = ("no_evidence", "low_confidence", "route_fail")
UNANSWERED_STATUSES = ("open", "resolved", "ignored")


class Trace(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "traces"
    __table_args__ = (
        enum_check("status", TRACE_STATUSES, "ck_traces_status"),
        Index("ix_traces_message_seq", "message_id", "seq"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    # 'route' / 'retrieve_exact_qa' / 'generate' ...
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="ok")
    # 摘要(长文本截断,原则:能看懂发生了什么即可)
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    model: Mapped[str | None] = mapped_column(Text)


class Feedback(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_feedbacks_message"),
        enum_check("vote", FEEDBACK_VOTES, "ck_feedbacks_vote"),
        enum_check("reason", FEEDBACK_REASONS, "ck_feedbacks_reason"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    vote: Mapped[str] = mapped_column(Text, nullable=False)
    # down 时选填
    reason: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class UnansweredItem(UUIDMixin, TimestampMixin, Base):
    """未命中问题池:知识运营的输入(哪些问题该补知识)。"""

    __tablename__ = "unanswered_pool"
    __table_args__ = (
        enum_check("reason", UNANSWERED_REASONS, "ck_unanswered_reason"),
        enum_check("status", UNANSWERED_STATUSES, "ck_unanswered_status"),
        Index("ix_unanswered_status", "status"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    resolved_note: Mapped[str | None] = mapped_column(Text)
