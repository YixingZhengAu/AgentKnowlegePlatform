"""S3 智能问数:语义层重审 + 已验证意图四张新表

字段级定义的唯一出处:documents/DB-DESIGN.md §4(本迁移是它的落地)。

做了四件事:
  1. 语义层三张表补列(同步时抓的物理注释/列序/键位、枚举的 value→meaning 结构、
     join 提示的来源留痕);`datasources.db_type` 放开到 mysql;
  2. 新建 `sql_intents` / `intent_questions` / `non_data_faces` / `intent_vectors`;
  3. **删除** `metrics` / `terms` / `rules` / `sql_examples`(废弃理由见 DB-DESIGN §4.9;
     四张表从建库起一直是空的,没有任何代码写过);
  4. `staging_items.item_type` 的 CHECK:去掉 table_meta / metric / term,加上 sql_intent
     (S3 只有"意图"一种候选进审核台,见 DB-DESIGN §8)。

⚠ 给集成者:这是 S3 域唯一的一份迁移,手写(没跑 autogenerate),down_revision 直接接在
initial_schema 上。若 S2 也在 initial 上挂了一份,合并时把这份 rebase 到那份之后即可
(本迁移与 S2 的表没有交集);也可以按 DB-DESIGN §10 折进 initial + `make db-reset`。
第 3、4 两件事碰到了共享表 `staging_items` 的 CHECK —— 那是必要的契约变更(域的 item_type
必须能落库),不是"顺手加自己需要的列"。

Revision ID: s3a1b2c3d4e5
Revises: 184b03b23dab
Create Date: 2026-08-23 21:00:00.000000

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.config import settings

# 向量维度由 EMBEDDING_DIM 决定,不硬编码(换 embedding 供应商 = 重建向量列)
EMBEDDING_DIM = settings.embedding_dim

# revision identifiers, used by Alembic.
revision: str = 's3a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '184b03b23dab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ===== 1. 废弃四张表(DB-DESIGN §4.9)=====
    op.drop_index('ix_sql_examples_kb_id', table_name='sql_examples')
    op.drop_index(
        'ix_sql_examples_embedding_hnsw', table_name='sql_examples',
        postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.drop_table('sql_examples')
    op.drop_index('ix_rules_kb_id', table_name='rules')
    op.drop_table('rules')
    op.drop_table('metrics')
    op.drop_table('terms')

    # ===== 2. 语义层补列 =====
    op.drop_constraint('ck_datasources_db_type', 'datasources', type_='check')
    op.create_check_constraint(
        'ck_datasources_db_type', 'datasources', "db_type IN ('mysql', 'postgres')")
    op.alter_column('datasources', 'db_type', server_default='mysql')
    op.add_column('datasources', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_datasources_kb_name', 'datasources', ['kb_id', 'name'])

    op.add_column('table_meta', sa.Column('physical_comment', sa.Text(), nullable=True))
    # schema_name 本来默认 'public';MySQL 下它是 database 名,没有合理默认值,去掉默认
    op.alter_column('table_meta', 'schema_name', server_default=None)

    op.add_column('column_meta', sa.Column('ordinal', sa.Integer(), nullable=True))
    op.add_column('column_meta', sa.Column('is_nullable', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('column_meta', sa.Column('key_flag', sa.Text(), nullable=True))
    op.add_column('column_meta', sa.Column('physical_comment', sa.Text(), nullable=True))
    op.add_column('column_meta', sa.Column('distinct_count', sa.Integer(), nullable=True))
    op.add_column('column_meta', sa.Column('is_enum_like', sa.Boolean(), server_default='false', nullable=False))

    op.add_column('relations', sa.Column('source', sa.Text(), server_default='foreign_key', nullable=False))
    op.create_check_constraint(
        'ck_relations_source', 'relations',
        "source IN ('foreign_key', 'heuristic', 'human')")
    op.create_unique_constraint(
        'uq_relations_edge', 'relations',
        ['datasource_id', 'from_table', 'from_column', 'to_table', 'to_column'])

    # ===== 3. 已验证意图四张新表 =====
    op.create_table(
        'sql_intents',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('datasource_id', sa.UUID(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('intent_type', sa.Text(), nullable=False),
        sa.Column('bucket', sa.Text(), nullable=True),
        sa.Column('one_liner', sa.Text(), nullable=False),
        sa.Column('brief', sa.Text(), nullable=False),
        sa.Column('tables', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('sql', sa.Text(), nullable=True),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.Text(), server_default='draft', nullable=False),
        sa.Column('prefill_rounds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('human_edited', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('source_staging_id', sa.UUID(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("intent_type IN ('query', 'stats')", name='ck_sql_intents_type'),
        sa.CheckConstraint("status IN ('draft', 'published', 'disabled')", name='ck_sql_intents_status'),
        sa.ForeignKeyConstraint(['datasource_id'], ['datasources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_staging_id'], ['staging_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kb_id', 'code', name='uq_sql_intents_kb_code'),
    )
    op.create_index('ix_sql_intents_datasource_id', 'sql_intents', ['datasource_id'], unique=False)
    op.create_index('ix_sql_intents_kb_status', 'sql_intents', ['kb_id', 'status'], unique=False)

    op.create_table(
        'intent_questions',
        sa.Column('intent_id', sa.UUID(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('origin', sa.Text(), server_default='ai', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'human')", name='ck_intent_questions_origin'),
        sa.ForeignKeyConstraint(['intent_id'], ['sql_intents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('intent_id', 'question_text', name='uq_intent_questions_text'),
    )

    op.create_table(
        'non_data_faces',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('face_text', sa.Text(), nullable=False),
        sa.Column('origin', sa.Text(), server_default='human', nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'human')", name='ck_non_data_faces_origin'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kb_id', 'face_text', name='uq_non_data_faces_text'),
    )

    op.create_table(
        'intent_vectors',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        # NULL = 空路由伪意图:它必须和真意图在同一次比较里竞争,所以住同一张索引表
        sa.Column('intent_id', sa.UUID(), nullable=True),
        sa.Column('face_kind', sa.Text(), nullable=False),
        sa.Column('face_text', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("face_kind IN ('summary', 'question', 'non_data')", name='ck_intent_vectors_face_kind'),
        sa.CheckConstraint("(face_kind = 'non_data') = (intent_id IS NULL)", name='ck_intent_vectors_null_route'),
        sa.ForeignKeyConstraint(['intent_id'], ['sql_intents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_intent_vectors_kb_id', 'intent_vectors', ['kb_id'], unique=False)
    op.create_index('ix_intent_vectors_intent_id', 'intent_vectors', ['intent_id'], unique=False)
    op.create_index(
        'ix_intent_vectors_embedding_hnsw', 'intent_vectors', ['embedding'], unique=False,
        postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'},
    )

    # ===== 4. staging_items.item_type 的枚举 =====
    op.drop_constraint('ck_staging_items_type', 'staging_items', type_='check')
    op.create_check_constraint(
        'ck_staging_items_type', 'staging_items',
        "item_type IN ('qa_pair', 'chunk', 'sql_intent')")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_staging_items_type', 'staging_items', type_='check')
    op.create_check_constraint(
        'ck_staging_items_type', 'staging_items',
        "item_type IN ('qa_pair', 'chunk', 'table_meta', 'metric', 'term')")

    op.drop_index(
        'ix_intent_vectors_embedding_hnsw', table_name='intent_vectors',
        postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.drop_index('ix_intent_vectors_intent_id', table_name='intent_vectors')
    op.drop_index('ix_intent_vectors_kb_id', table_name='intent_vectors')
    op.drop_table('intent_vectors')
    op.drop_table('non_data_faces')
    op.drop_table('intent_questions')
    op.drop_index('ix_sql_intents_kb_status', table_name='sql_intents')
    op.drop_index('ix_sql_intents_datasource_id', table_name='sql_intents')
    op.drop_table('sql_intents')

    op.drop_constraint('uq_relations_edge', 'relations', type_='unique')
    op.drop_constraint('ck_relations_source', 'relations', type_='check')
    op.drop_column('relations', 'source')
    for col in ('is_enum_like', 'distinct_count', 'physical_comment', 'key_flag',
                'is_nullable', 'ordinal'):
        op.drop_column('column_meta', col)
    op.alter_column('table_meta', 'schema_name', server_default='public')
    op.drop_column('table_meta', 'physical_comment')
    op.drop_constraint('uq_datasources_kb_name', 'datasources', type_='unique')
    op.drop_column('datasources', 'last_synced_at')
    op.alter_column('datasources', 'db_type', server_default='postgres')
    op.drop_constraint('ck_datasources_db_type', 'datasources', type_='check')
    op.create_check_constraint(
        'ck_datasources_db_type', 'datasources', "db_type IN ('postgres')")

    # 四张废弃表按 initial_schema 的定义重建(内容无法恢复,它们本来一直是空的)
    op.create_table(
        'terms',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('term', sa.Text(), nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kb_id', 'term', name='uq_terms_kb_term'),
    )
    op.create_table(
        'metrics',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('definition_sql', sa.Text(), nullable=False),
        sa.Column('unit', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default='enabled', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('enabled', 'disabled')", name='ck_metrics_status'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kb_id', 'name', name='uq_metrics_kb_name'),
    )
    op.create_table(
        'rules',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('rule_type', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("rule_type IN ('scope', 'filter', 'style')", name='ck_rules_type'),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rules_kb_id', 'rules', ['kb_id'], unique=False)
    op.create_table(
        'sql_examples',
        sa.Column('kb_id', sa.UUID(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('sql', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(EMBEDDING_DIM), nullable=True),
        sa.Column('verified', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_sql_examples_embedding_hnsw', 'sql_examples', ['embedding'], unique=False,
        postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.create_index('ix_sql_examples_kb_id', 'sql_examples', ['kb_id'], unique=False)
