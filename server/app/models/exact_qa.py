"""精准 QA 域:命中即原样返回,零改写(PRD 的零幻觉承诺就落在这两张表上)。

一问一向量:标准问 + 每个相似问各占 exact_qa_vectors 一行。
维护规则:item 的问题集合变化时,应用层全删重建该 item 的向量行。
"""

import datetime as dt
import uuid

from sqlalchemy import Date, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import embedding_column_type
from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

QA_STATUSES = ("enabled", "disabled")


class ExactQaItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "exact_qa_items"
    __table_args__ = (
        enum_check("status", QA_STATUSES, "ck_exact_qa_items_status"),
        Index("ix_exact_qa_items_kb_status", "kb_id", "status"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    standard_question: Mapped[str] = mapped_column(Text, nullable=False)
    # 命中 >=0.90 时原样返回、零改写的那个答案
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    similar_questions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    # 有效期,NULL=不限;检索时过滤过期条目
    effective_from: Mapped[dt.date | None] = mapped_column(Date)
    effective_to: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="enabled")
    # 溯源:来自哪条审核记录(弱引用,断了不影响正式数据)
    source_staging_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("staging_items.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ExactQaVector(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "exact_qa_vectors"
    __table_args__ = (
        UniqueConstraint("item_id", "question_text", name="uq_exact_qa_vectors_item_question"),
        Index("ix_exact_qa_vectors_item_id", "item_id"),
        Index(
            "ix_exact_qa_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exact_qa_items.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(embedding_column_type(), nullable=False)
