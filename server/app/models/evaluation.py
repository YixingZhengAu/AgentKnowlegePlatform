"""评测域(S0 建表,S6 使用;D4 的"留口子")。

eval_runs.config_snapshot 是两次跑分可比的前提;
eval_cases.source_message_id 是"从对话加入评测集"按钮的溯源。
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

RUN_STATUSES = ("queued", "running", "finished", "failed")
JUDGE_VERDICTS = ("pass", "fail", "unsure")


class EvalSet(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "eval_sets"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class EvalCase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "eval_cases"
    __table_args__ = (Index("ix_eval_cases_set_id", "set_id"),)

    set_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # LLM judge 的比对基准
    expected_answer: Mapped[str | None] = mapped_column(Text)
    # 期望命中的知识类型
    expected_route: Mapped[str | None] = mapped_column(Text)
    expected_citations: Mapped[list | None] = mapped_column(JSONB)
    # "从对话加入评测集"的溯源(弱引用)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class EvalRun(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "eval_runs"
    __table_args__ = (
        enum_check("status", RUN_STATUSES, "ck_eval_runs_status"),
        Index("ix_eval_runs_set_id", "set_id"),
    )

    set_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    # 跑分时 agent + 绑定配置的快照
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    # {"pass_rate":0.86,"avg_latency_ms":1200}
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class EvalResult(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "eval_results"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", name="uq_eval_results_run_case"),
        enum_check("judge_verdict", JUDGE_VERDICTS, "ck_eval_results_verdict"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("eval_cases.id", ondelete="CASCADE"), nullable=False
    )
    # 实际回答(通过 run_chat() 产生)
    answer: Mapped[str | None] = mapped_column(Text)
    route_actual: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB)
    judge_verdict: Mapped[str | None] = mapped_column(Text)
    judge_reason: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    usage: Mapped[dict | None] = mapped_column(JSONB)
