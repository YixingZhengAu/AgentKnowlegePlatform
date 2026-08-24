"""智能问数域:语义层 + 已验证意图。字段级定义的唯一出处是 `documents/DB-DESIGN.md` §4。

两组表,职责完全不同:

* **语义层**(`datasources` / `table_meta` / `column_meta` / `relations`)——
  运营可维护的治理资产,不是"自动抓一遍就完事"的 schema 缓存。它喂的是**生成期**
  (写模板 SQL 的那次 LLM 调用),不是运行时。
* **已验证意图**(`sql_intents` / `intent_questions` / `non_data_faces` / `intent_vectors`)——
  运行时唯一会被执行的 SQL 的来源。运行时**不生成 SQL**,只在模板的参数区内做受约束改写。

★ 为什么没有 metrics / terms / rules / sql_examples:见 DB-DESIGN §4.9。它们服务的是
  "自由生成 + few-shot"路线;模板路线里指标口径焊死在 `sql_intents.sql` 并经人工验收,
  再留一份可漂移的口径定义就是给同一件事留两个出处。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._types import embedding_column_type
from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, enum_check

#: 演示库是 MySQL;PG 留着是因为 introspection 走的是 information_schema,换库只换方言
DB_TYPES = ("mysql", "postgres")
DATASOURCE_STATUSES = ("active", "disabled")
RELATION_TYPES = ("many_to_one", "one_to_one")
#: join 提示的来源必须留痕:真 FK 与命名启发式猜出来的可信度不同,人审时要能一眼分开
RELATION_SOURCES = ("foreign_key", "heuristic", "human")
#: 意图分型决定模板生成策略与参数区形状,不是标签
INTENT_TYPES = ("query", "stats")
INTENT_STATUSES = ("draft", "published", "disabled")
#: 索引面的三种来源(评审报告要能回答"哪一类面在真正干活")
FACE_KINDS = ("summary", "question", "non_data")
ASSET_ORIGINS = ("ai", "human")


def _kb_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )


def _datasource_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )


# ============================================================ 语义层


class Datasource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "datasources"
    __table_args__ = (
        UniqueConstraint("kb_id", "name", name="uq_datasources_kb_name"),
        enum_check("db_type", DB_TYPES, "ck_datasources_db_type"),
        enum_check("status", DATASOURCE_STATUSES, "ck_datasources_status"),
        Index("ix_datasources_kb_id", "kb_id"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    db_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="mysql")
    # 连接串用 Fernet 对称加密,密钥来自 env SECRET_KEY。明文永不落库、永不出接口
    dsn_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # 运维确认该账号只读;false 时执行闸直接拒(不是提示,是拒)
    readonly_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    # 最近一次 schema 同步完成时间(前端据此显示"元数据是否过期")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TableMeta(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "table_meta"
    __table_args__ = (
        UniqueConstraint("datasource_id", "schema_name", "table_name", name="uq_table_meta_ident"),
    )

    datasource_id: Mapped[uuid.UUID] = _datasource_fk()
    # MySQL 下就是 database 名(demo_biz);PG 下是 schema
    schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    # 给 LLM 的表用途说明,AI 预填 + 人工确认
    description: Mapped[str | None] = mapped_column(Text)
    # 库里原本的表注释:是治理素材,不是成品(演示库刻意只有一部分表列有注释)
    physical_comment: Mapped[str | None] = mapped_column(Text)
    # 治理开关:是否纳入问数范围
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    row_count_estimate: Mapped[int | None] = mapped_column(BigInteger)


class ColumnMeta(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "column_meta"
    __table_args__ = (
        UniqueConstraint("table_meta_id", "column_name", name="uq_column_meta_ident"),
    )

    table_meta_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("table_meta.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    # 库里的列序:前端表格按它排(按字母排会把主键排到中间)
    ordinal: Mapped[int | None] = mapped_column(Integer)
    data_type: Mapped[str | None] = mapped_column(Text)
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # PRI / UNI / MUL —— join 提示与主键识别都要它
    key_flag: Mapped[str | None] = mapped_column(Text)
    physical_comment: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    # true 时模板生成与运行时改写都禁止 SELECT 此列
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    distinct_count: Mapped[int | None] = mapped_column(Integer)
    is_enum_like: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # [{"value": "NSW", "meaning": "New South Wales."}] —— 改写阶段真正需要的是"值→含义",
    # 模型才敢把"新南威尔士的单"映射到 NSW。裸 string[] 给不了这个
    enum_values: Mapped[list | None] = mapped_column(JSONB)
    # 同步时采样 <=5 个值(截断到 80 字符),帮模型理解格式
    sample_values: Mapped[list | None] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Relation(UUIDMixin, CreatedAtMixin, Base):
    """join 提示:告诉生成期的模型表之间怎么连。"""

    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint(
            "datasource_id", "from_table", "from_column", "to_table", "to_column",
            name="uq_relations_edge",
        ),
        enum_check("relation_type", RELATION_TYPES, "ck_relations_type"),
        enum_check("source", RELATION_SOURCES, "ck_relations_source"),
        Index("ix_relations_datasource_id", "datasource_id"),
    )

    datasource_id: Mapped[uuid.UUID] = _datasource_fk()
    from_table: Mapped[str] = mapped_column(Text, nullable=False)
    from_column: Mapped[str] = mapped_column(Text, nullable=False)
    to_table: Mapped[str] = mapped_column(Text, nullable=False)
    to_column: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="foreign_key")
    description: Mapped[str | None] = mapped_column(Text)


# ============================================================ 已验证意图


class SqlIntent(UUIDMixin, TimestampMixin, Base):
    """★ 本域的核心表:意图 = 已验收的 SQL 模板 + 参数区。

    一条 intent 就是"一类能被准确回答的数据问题"。它不是 few-shot 素材,
    是**运行时唯一会被执行的 SQL 的来源**。
    """

    __tablename__ = "sql_intents"
    __table_args__ = (
        UniqueConstraint("kb_id", "code", name="uq_sql_intents_kb_code"),
        enum_check("intent_type", INTENT_TYPES, "ck_sql_intents_type"),
        enum_check("status", INTENT_STATUSES, "ck_sql_intents_status"),
        Index("ix_sql_intents_datasource_id", "datasource_id"),
        Index("ix_sql_intents_kb_status", "kb_id", "status"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    # 模板绑死在某个数据源上(SQL 方言与表名都是它的)
    datasource_id: Mapped[uuid.UUID] = _datasource_fk()
    # 人可见的稳定短标识(i01...):报告 / trace / 评测集都引它,换 uuid 会让人审材料失去可读性
    code: Mapped[str] = mapped_column(Text, nullable=False)
    intent_type: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str | None] = mapped_column(Text)
    # 带 Query:/Stats: 治理前缀;进索引前会剥掉 —— 前缀是内部标签,用户问句里绝不会出现
    one_liner: Mapped[str] = mapped_column(Text, nullable=False)
    # 说明书体详述(给模板生成与人审看)。刻意不进检索索引:B7 消融实测零增益且制造冲突
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    tables: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    sql: Mapped[str | None] = mapped_column(Text)
    # 参数区三段结构(filters / outputs / groupbys),见 DB-DESIGN §4.8
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    # 参数区 AI 预填用了几轮(含回灌自修),质量留痕
    prefill_rounds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    human_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 溯源到候选(与 S1 同一条纪律:正式表不复制 origin_ref)
    source_staging_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("staging_items.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntentQuestion(UUIDMixin, TimestampMixin, Base):
    """相似问法:可编辑子资产。检索时比的是**问句 vs 问句**,不是问句 vs 说明文。

    本表不存向量(向量在 `intent_vectors`)—— 问法集合一变就全删重建索引面,
    把向量挂在可编辑资产行上就得处理"改一条、删一条、又加回来"的组合,是自找麻烦。
    """

    __tablename__ = "intent_questions"
    __table_args__ = (
        UniqueConstraint("intent_id", "question_text", name="uq_intent_questions_text"),
        enum_check("origin", ASSET_ORIGINS, "ck_intent_questions_origin"),
    )

    intent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sql_intents.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai")


class NonDataFace(UUIDMixin, TimestampMixin, Base):
    """空路由负例面:"以上都不是"的示例(产品规格 / 质保 / 操作手册 / 流程政策 / 闲聊)。

    ★ 为什么必须有这张表(B8 实测逼出来的):
    "What's the warranty period on the HC-300 battery cabinet?" 会**确信地**命中库存流水
    意图(0.5183 / 边距 0.2575),因为它和一条含产品全名的相似问法共享产品名。调阈值救不了 ——
    0.5183 高于应命中类最低分 0.4981,抬阈值必先误杀真正例。区分它靠的不是分数高低,
    而是索引里**有没有一个更像的负例**。
    """

    __tablename__ = "non_data_faces"
    __table_args__ = (
        UniqueConstraint("kb_id", "face_text", name="uq_non_data_faces_text"),
        enum_check("origin", ASSET_ORIGINS, "ck_non_data_faces_origin"),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    face_text: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="human")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class IntentVector(UUIDMixin, CreatedAtMixin, Base):
    """索引面:一面一行。运行时检索的唯一数据来源。

    维护规则(与 S1 的 exact_qa_vectors 同一条):意图发布 / 相似问法保存 / 负例面保存
    → **全删重建**对应的面,不做增量 diff。
    """

    __tablename__ = "intent_vectors"
    __table_args__ = (
        enum_check("face_kind", FACE_KINDS, "ck_intent_vectors_face_kind"),
        # 两边必须同时成立,防出现"挂在真意图上的负例面"这种脏数据
        CheckConstraint(
            "(face_kind = 'non_data') = (intent_id IS NULL)",
            name="ck_intent_vectors_null_route",
        ),
        Index("ix_intent_vectors_kb_id", "kb_id"),
        Index("ix_intent_vectors_intent_id", "intent_id"),
        Index(
            "ix_intent_vectors_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    kb_id: Mapped[uuid.UUID] = _kb_fk()
    # NULL = 空路由伪意图(__non_data__)。**这一列可空是本域最需要解释的设计**:
    # 空路由要能和真意图在同一次比较里竞争,才可能"比所有真意图都更像",
    # 所以它必须住在同一张索引表里
    intent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sql_intents.id", ondelete="CASCADE")
    )
    face_kind: Mapped[str] = mapped_column(Text, nullable=False)
    # 被嵌入的原文(已剥掉治理前缀)
    face_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(embedding_column_type(), nullable=False)
