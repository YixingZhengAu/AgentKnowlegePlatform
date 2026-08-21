"""摄取骨架域(三类知识共用):原料 -> 异步加工 Job -> 人工审核 Staging -> 发布。

这是 PRD §3.1.1 通用摄取工作流的落地,也是 S0 就要跑通的机制:
S1/S2/S3 只贡献各自的 Job 子类、渲染器与 publisher,这四张表不变。
"""

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
)
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, REAL
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

SOURCE_TYPES = ("file", "text", "db_sync")
JOB_STATUSES = (
    "queued",
    "running",
    "review",
    "publishing",
    "published",
    "failed",
    "cancelled",
)
ITEM_TYPES = ("qa_pair", "chunk", "table_meta", "metric", "term")
REVIEW_STATUSES = ("pending", "approved", "rejected", "modified")
# 心跳超时判定僵尸任务的阈值(秒),执行器与启动清理共用
JOB_HEARTBEAT_TIMEOUT_SEC = 60


class IngestSource(UUIDMixin, CreatedAtMixin, Base):
    """上传的原料:文件、纯文本或一次 schema 同步。"""

    __tablename__ = "ingest_sources"
    __table_args__ = (
        enum_check("source_type", SOURCE_TYPES, "ck_ingest_sources_type"),
        Index("ix_ingest_sources_kb_id", "kb_id"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    # FILE_STORAGE_DIR 下相对路径;source_type='text' 时为 NULL
    uri: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BIGINT)
    mime: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class IngestJob(UUIDMixin, CreatedAtMixin, Base):
    """异步加工任务。

    状态机:queued -> running -> review -(用户点发布)-> publishing -> published
            running/publishing -> failed(可从失败步骤重跑);review -> cancelled
    steps 是声明式的:[{"name":"parse","title":"Parse document"}],前端进度条直接渲染它。
    """

    __tablename__ = "ingest_jobs"
    __table_args__ = (
        enum_check("status", JOB_STATUSES, "ck_ingest_jobs_status"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_ingest_jobs_progress"),
        Index("ix_ingest_jobs_status", "status"),
        Index("ix_ingest_jobs_kb_created", "kb_id", "created_at"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingest_sources.id", ondelete="SET NULL")
    )
    # 'qa_extract' / 'doc_pipeline' / 'schema_sync' / 'demo_sleep'(S0 假任务)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    current_step: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    step_logs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    error: Mapped[dict | None] = mapped_column(JSONB)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # 执行器定期更新;启动时把「running 且心跳超时」的置 failed(僵尸处理)
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class StagingItem(UUIDMixin, TimestampMixin, Base):
    """待审核的加工产物:item_type 决定前端用哪个渲染器,payload 结构见 DB-DESIGN §8。"""

    __tablename__ = "staging_items"
    __table_args__ = (
        enum_check("item_type", ITEM_TYPES, "ck_staging_items_type"),
        enum_check("review_status", REVIEW_STATUSES, "ck_staging_items_review_status"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_staging_items_confidence",
        ),
        Index("ix_staging_items_job_review", "job_id", "review_status"),
        Index("ix_staging_items_kb_type", "kb_id", "item_type"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # 溯源定位:{"source_id":"...","page":3,"quote":"..."}
    origin_ref: Mapped[dict | None] = mapped_column(JSONB)
    # 抽取置信度,审核列表按它排序
    confidence: Mapped[float | None] = mapped_column(REAL)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 发布后指向正式表:{"table":"exact_qa_items","id":"..."}
    published_ref: Mapped[dict | None] = mapped_column(JSONB)
    # 冲突检测结果:[{"item_id":"...","similarity":0.97}]
    conflict_with: Mapped[list | None] = mapped_column(JSONB)


class PublishRecord(UUIDMixin, CreatedAtMixin, Base):
    """发布审计:哪次 job、发布了多少条、谁点的。"""

    __tablename__ = "publish_records"
    __table_args__ = (Index("ix_publish_records_job_id", "job_id"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    # {"approved":18,"modified":4,"rejected":2}
    item_counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
