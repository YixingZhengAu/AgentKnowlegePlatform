"""文档 RAG 域:documents(原始文档)+ chunks(切片,向量 + 全文双索引)。"""

import uuid

from sqlalchemy import Computed, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import embedding_column_type
from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

FILE_TYPES = ("pdf", "docx", "md", "txt", "html", "xlsx")
PARSE_STATUSES = ("pending", "parsing", "parsed", "failed")

#: 已发布切片的启用/禁用软标志。**不物理删** —— 它可能已被
#: `message_citations.ref_id` 引用过,删了历史会话的引用就悬空(DB-DESIGN §3)
CHUNK_STATUSES = ("active", "disabled")


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        enum_check("file_type", FILE_TYPES, "ck_documents_file_type"),
        enum_check("parse_status", PARSE_STATUSES, "ck_documents_parse_status"),
        Index("ix_documents_kb_id", "kb_id"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingest_sources.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(Text)
    # FILE_STORAGE_DIR 下的相对路径
    raw_uri: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BIGINT)
    parse_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Chunk(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        # 🩸 **只约束在用的行**。退休行(被引用过、被新一版取代)保留它原来的 `seq`,
        # 于是同一个 seq 可以有一条 active 加若干条历史存根 —— 而"一份文档同一时刻
        # 只有一条 seq=N 在用"这个真正要保证的东西,由 WHERE 子句写明了。
        # 旧写法是把退休行的 seq 挪进负号区,那套编码**跨代不唯一**(同一个 seq
        # 退休两次会撞同一个槽),2026-08-25 实测炸在这里。
        Index(
            "uq_chunks_doc_seq_active",
            "doc_id",
            "seq",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_chunks_doc_id", "doc_id"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv_gin", "tsv", postgresql_using="gin"),
        enum_check("status", CHUNK_STATUSES, "ck_chunks_status"),
    )

    doc_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    # 文档内顺序,上下文扩展(取前后块)靠它
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 如 "Installation Manual > 3 Wiring > 3.2 DC side",会拼进 embedding 输入
    heading_path: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    # 离线 HyDE:预生成的假设性问题
    hypo_questions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(embedding_column_type())
    # S0 用 simple 分词占位;S2 评估中文/英文分词方案时改这个生成列
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True)
    )
    # 🩸 下线是软标志,不是删行。禁用时 **embedding 一并清空**(照 S1"下线 = 删向量行"),
    # 两条召回 SQL 都要过滤 `status='active'` —— 漏一条就是"下线了还能被搜到"
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    # 页码、bbox 等定位信息(引用跳原文用)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
