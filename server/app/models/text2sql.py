"""智能问数域:语义层即知识 —— 表/列元数据、关系、指标口径、术语、规则、few-shot 示例。

这里的每张表都是"运营可维护的治理资产",不是自动抓取就完事的 schema 缓存。
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import BIGINT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import embedding_column_type
from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

DB_TYPES = ("postgres",)
DATASOURCE_STATUSES = ("active", "disabled")
RELATION_TYPES = ("many_to_one", "one_to_one")
METRIC_STATUSES = ("enabled", "disabled")
RULE_TYPES = ("scope", "filter", "style")


def _kb_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )


class Datasource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "datasources"
    __table_args__ = (
        enum_check("db_type", DB_TYPES, "ck_datasources_db_type"),
        enum_check("status", DATASOURCE_STATUSES, "ck_datasources_status"),
        Index("ix_datasources_kb_id", "kb_id"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    db_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="postgres")
    # 连接串用 Fernet 对称加密,密钥来自 env SECRET_KEY
    dsn_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # 运维确认该账号只读;false 时问数功能拒绝执行(安全闸门)
    readonly_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class TableMeta(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "table_meta"
    __table_args__ = (
        UniqueConstraint("datasource_id", "schema_name", "table_name", name="uq_table_meta_ident"),
    )

    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    schema_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="public")
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # 给 LLM 的表用途说明
    description: Mapped[str | None] = mapped_column(Text)
    # 治理开关:是否纳入问数范围
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    row_count_estimate: Mapped[int | None] = mapped_column(BIGINT)


class ColumnMeta(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "column_meta"
    __table_args__ = (
        UniqueConstraint("table_meta_id", "column_name", name="uq_column_meta_ident"),
    )

    table_meta_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("table_meta.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    # true 时生成的 SQL 禁止 SELECT 此列
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 低基数列取值字典,如 ["NSW","VIC"],直接进 prompt
    enum_values: Mapped[list | None] = mapped_column(JSONB)
    # 同步时采样 3-5 个值,帮 LLM 理解格式
    sample_values: Mapped[list | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Relation(UUIDMixin, CreatedAtMixin, Base):
    """join 提示:告诉 LLM 表之间怎么连。"""

    __tablename__ = "relations"
    __table_args__ = (
        enum_check("relation_type", RELATION_TYPES, "ck_relations_type"),
        Index("ix_relations_datasource_id", "datasource_id"),
    )

    datasource_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    from_table: Mapped[str] = mapped_column(Text, nullable=False)
    from_column: Mapped[str] = mapped_column(Text, nullable=False)
    to_table: Mapped[str] = mapped_column(Text, nullable=False)
    to_column: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class Metric(UUIDMixin, TimestampMixin, Base):
    """指标口径:"销售额"到底怎么算,由这里定,不由 LLM 猜。"""

    __tablename__ = "metrics"
    __table_args__ = (
        UniqueConstraint("kb_id", "name", name="uq_metrics_kb_name"),
        enum_check("status", METRIC_STATUSES, "ck_metrics_status"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # 如 SUM(oi.qty * oi.unit_price)
    definition_sql: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="enabled")


class Term(UUIDMixin, TimestampMixin, Base):
    """业务术语映射:自然语言里的说法 -> 数据里的口径。"""

    __tablename__ = "terms"
    __table_args__ = (UniqueConstraint("kb_id", "term", name="uq_terms_kb_term"),)

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    term: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


class Rule(UUIDMixin, CreatedAtMixin, Base):
    """问数全局规则:范围限制 / 默认过滤 / 输出风格。"""

    __tablename__ = "rules"
    __table_args__ = (
        enum_check("rule_type", RULE_TYPES, "ck_rules_type"),
        Index("ix_rules_kb_id", "kb_id"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class SqlExample(UUIDMixin, TimestampMixin, Base):
    """few-shot 示范:按 question 嵌入,运行时检索最相似的几条进 prompt。"""

    __tablename__ = "sql_examples"
    __table_args__ = (
        Index("ix_sql_examples_kb_id", "kb_id"),
        Index(
            "ix_sql_examples_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(embedding_column_type())
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
