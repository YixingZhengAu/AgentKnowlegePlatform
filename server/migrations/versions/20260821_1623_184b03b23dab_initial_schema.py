"""initial schema:全部业务表一次建齐

字段级定义的唯一出处:documents/DB-DESIGN.md。
改表流程见该文档 §10。

Revision ID: 184b03b23dab
Revises: 
Create Date: 2026-08-21 16:23:54.054114

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
revision: str = '184b03b23dab'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 自成一体:即使不是 docker init 建的库,迁移也能跑
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table('agents',
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('router_mode', sa.Text(), server_default='rule_llm', nullable=False),
    sa.Column('model_cfg', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('fallback_reply', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='active', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("router_mode IN ('rule_llm', 'llm_only')", name='ck_agents_router_mode'),
    sa.CheckConstraint("status IN ('active', 'archived')", name='ck_agents_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('eval_sets',
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('username', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('conversations',
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='active', nullable=False),
    sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('active', 'archived')", name='ck_conversations_status'),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_user_last_message', 'conversations', ['user_id', 'last_message_at'], unique=False)
    op.create_table('eval_runs',
    sa.Column('set_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Text(), server_default='queued', nullable=False),
    sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued', 'running', 'finished', 'failed')", name='ck_eval_runs_status'),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['set_id'], ['eval_sets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_eval_runs_set_id', 'eval_runs', ['set_id'], unique=False)
    op.create_table('knowledge_bases',
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Text(), server_default='active', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('active', 'archived')", name='ck_knowledge_bases_status'),
    sa.CheckConstraint("type IN ('exact_qa', 'document', 'text2sql')", name='ck_knowledge_bases_type'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_bases_owner_id', 'knowledge_bases', ['owner_id'], unique=False)
    op.create_table('agent_kb_bindings',
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('priority', sa.Integer(), server_default='100', nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('top_k', sa.Integer(), nullable=True),
    sa.Column('threshold', sa.REAL(), nullable=True),
    sa.Column('usage_desc', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_id', 'kb_id', name='uq_agent_kb_bindings')
    )
    op.create_index('ix_agent_kb_bindings_agent_id', 'agent_kb_bindings', ['agent_id'], unique=False)
    op.create_table('datasources',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('db_type', sa.Text(), server_default='postgres', nullable=False),
    sa.Column('dsn_enc', sa.Text(), nullable=False),
    sa.Column('readonly_confirmed', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('status', sa.Text(), server_default='active', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("db_type IN ('postgres')", name='ck_datasources_db_type'),
    sa.CheckConstraint("status IN ('active', 'disabled')", name='ck_datasources_status'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_datasources_kb_id', 'datasources', ['kb_id'], unique=False)
    op.create_table('ingest_sources',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('source_type', sa.Text(), nullable=False),
    sa.Column('original_name', sa.Text(), nullable=True),
    sa.Column('uri', sa.Text(), nullable=True),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('size_bytes', sa.BIGINT(), nullable=True),
    sa.Column('mime', sa.Text(), nullable=True),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source_type IN ('file', 'text', 'db_sync')", name='ck_ingest_sources_type'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingest_sources_kb_id', 'ingest_sources', ['kb_id'], unique=False)
    op.create_table('messages',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default='completed', nullable=False),
    sa.Column('route_decision', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_messages_role'),
    sa.CheckConstraint("status IN ('completed', 'failed', 'interrupted')", name='ck_messages_status'),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_table('metrics',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('definition_sql', sa.Text(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default='enabled', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('enabled', 'disabled')", name='ck_metrics_status'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kb_id', 'name', name='uq_metrics_kb_name')
    )
    op.create_table('rules',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('rule_type', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("rule_type IN ('scope', 'filter', 'style')", name='ck_rules_type'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rules_kb_id', 'rules', ['kb_id'], unique=False)
    op.create_table('sql_examples',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('sql', sa.Text(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=EMBEDDING_DIM), nullable=True),
    sa.Column('verified', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sql_examples_embedding_hnsw', 'sql_examples', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_sql_examples_kb_id', 'sql_examples', ['kb_id'], unique=False)
    op.create_table('terms',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('term', sa.Text(), nullable=False),
    sa.Column('definition', sa.Text(), nullable=False),
    sa.Column('aliases', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kb_id', 'term', name='uq_terms_kb_term')
    )
    op.create_table('documents',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('file_type', sa.Text(), nullable=True),
    sa.Column('raw_uri', sa.Text(), nullable=True),
    sa.Column('size_bytes', sa.BIGINT(), nullable=True),
    sa.Column('parse_status', sa.Text(), server_default='pending', nullable=False),
    sa.Column('parse_error', sa.Text(), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("file_type IN ('pdf', 'docx', 'md', 'txt', 'html', 'xlsx')", name='ck_documents_file_type'),
    sa.CheckConstraint("parse_status IN ('pending', 'parsing', 'parsed', 'failed')", name='ck_documents_parse_status'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['ingest_sources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_kb_id', 'documents', ['kb_id'], unique=False)
    op.create_table('eval_cases',
    sa.Column('set_id', sa.UUID(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('expected_answer', sa.Text(), nullable=True),
    sa.Column('expected_route', sa.Text(), nullable=True),
    sa.Column('expected_citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('source_message_id', sa.UUID(), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['set_id'], ['eval_sets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_eval_cases_set_id', 'eval_cases', ['set_id'], unique=False)
    op.create_table('feedbacks',
    sa.Column('message_id', sa.UUID(), nullable=False),
    sa.Column('vote', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("reason IN ('wrong', 'incomplete', 'irrelevant', 'other')", name='ck_feedbacks_reason'),
    sa.CheckConstraint("vote IN ('up', 'down')", name='ck_feedbacks_vote'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id', name='uq_feedbacks_message')
    )
    op.create_table('ingest_jobs',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('job_type', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default='queued', nullable=False),
    sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('current_step', sa.Text(), nullable=True),
    sa.Column('progress', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('step_logs', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued', 'running', 'review', 'publishing', 'published', 'failed', 'cancelled')", name='ck_ingest_jobs_status'),
    sa.CheckConstraint('progress >= 0 AND progress <= 100', name='ck_ingest_jobs_progress'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['ingest_sources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingest_jobs_kb_created', 'ingest_jobs', ['kb_id', 'created_at'], unique=False)
    op.create_index('ix_ingest_jobs_status', 'ingest_jobs', ['status'], unique=False)
    op.create_table('message_citations',
    sa.Column('message_id', sa.UUID(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('citation_type', sa.Text(), nullable=False),
    sa.Column('ref_id', sa.UUID(), nullable=True),
    sa.Column('snippet', sa.Text(), nullable=True),
    sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("citation_type IN ('exact_qa', 'chunk', 'sql')", name='ck_message_citations_type'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id', 'seq', name='uq_message_citations_seq')
    )
    op.create_table('relations',
    sa.Column('datasource_id', sa.UUID(), nullable=False),
    sa.Column('from_table', sa.Text(), nullable=False),
    sa.Column('from_column', sa.Text(), nullable=False),
    sa.Column('to_table', sa.Text(), nullable=False),
    sa.Column('to_column', sa.Text(), nullable=False),
    sa.Column('relation_type', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("relation_type IN ('many_to_one', 'one_to_one')", name='ck_relations_type'),
    sa.ForeignKeyConstraint(['datasource_id'], ['datasources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_relations_datasource_id', 'relations', ['datasource_id'], unique=False)
    op.create_table('table_meta',
    sa.Column('datasource_id', sa.UUID(), nullable=False),
    sa.Column('schema_name', sa.Text(), server_default='public', nullable=False),
    sa.Column('table_name', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('row_count_estimate', sa.BIGINT(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['datasource_id'], ['datasources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('datasource_id', 'schema_name', 'table_name', name='uq_table_meta_ident')
    )
    op.create_table('traces',
    sa.Column('message_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.Text(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('status', sa.Text(), server_default='ok', nullable=False),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('prompt_tokens', sa.Integer(), nullable=True),
    sa.Column('completion_tokens', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('model', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ok', 'error')", name='ck_traces_status'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_traces_message_seq', 'traces', ['message_id', 'seq'], unique=False)
    op.create_table('unanswered_pool',
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('message_id', sa.UUID(), nullable=True),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default='open', nullable=False),
    sa.Column('resolved_note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("reason IN ('no_evidence', 'low_confidence', 'route_fail')", name='ck_unanswered_reason'),
    sa.CheckConstraint("status IN ('open', 'resolved', 'ignored')", name='ck_unanswered_status'),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_unanswered_status', 'unanswered_pool', ['status'], unique=False)
    op.create_table('chunks',
    sa.Column('doc_id', sa.UUID(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('heading_path', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('hypo_questions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=EMBEDDING_DIM), nullable=True),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('simple', content)", persisted=True), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['doc_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('doc_id', 'seq', name='uq_chunks_doc_seq')
    )
    op.create_index('ix_chunks_doc_id', 'chunks', ['doc_id'], unique=False)
    op.create_index('ix_chunks_embedding_hnsw', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_chunks_tsv_gin', 'chunks', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('column_meta',
    sa.Column('table_meta_id', sa.UUID(), nullable=False),
    sa.Column('column_name', sa.Text(), nullable=False),
    sa.Column('data_type', sa.Text(), nullable=True),
    sa.Column('display_name', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_sensitive', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('enum_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sample_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['table_meta_id'], ['table_meta.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('table_meta_id', 'column_name', name='uq_column_meta_ident')
    )
    op.create_table('eval_results',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=True),
    sa.Column('route_actual', sa.Text(), nullable=True),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('judge_verdict', sa.Text(), nullable=True),
    sa.Column('judge_reason', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("judge_verdict IN ('pass', 'fail', 'unsure')", name='ck_eval_results_verdict'),
    sa.ForeignKeyConstraint(['case_id'], ['eval_cases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['eval_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'case_id', name='uq_eval_results_run_case')
    )
    op.create_table('publish_records',
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('item_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('published_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['ingest_jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['published_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_publish_records_job_id', 'publish_records', ['job_id'], unique=False)
    op.create_table('staging_items',
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('item_type', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('origin_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('confidence', sa.REAL(), nullable=True),
    sa.Column('review_status', sa.Text(), server_default='pending', nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('published_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('conflict_with', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("item_type IN ('qa_pair', 'chunk', 'table_meta', 'metric', 'term')", name='ck_staging_items_type'),
    sa.CheckConstraint("review_status IN ('pending', 'approved', 'rejected', 'modified')", name='ck_staging_items_review_status'),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name='ck_staging_items_confidence'),
    sa.ForeignKeyConstraint(['job_id'], ['ingest_jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_staging_items_job_review', 'staging_items', ['job_id', 'review_status'], unique=False)
    op.create_index('ix_staging_items_kb_type', 'staging_items', ['kb_id', 'item_type'], unique=False)
    op.create_table('exact_qa_items',
    sa.Column('kb_id', sa.UUID(), nullable=False),
    sa.Column('standard_question', sa.Text(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('similar_questions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('keywords', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=True),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('status', sa.Text(), server_default='enabled', nullable=False),
    sa.Column('source_staging_id', sa.UUID(), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('enabled', 'disabled')", name='ck_exact_qa_items_status'),
    sa.ForeignKeyConstraint(['kb_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_staging_id'], ['staging_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exact_qa_items_kb_status', 'exact_qa_items', ['kb_id', 'status'], unique=False)
    op.create_table('exact_qa_vectors',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('question_text', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=EMBEDDING_DIM), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['exact_qa_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'question_text', name='uq_exact_qa_vectors_item_question')
    )
    op.create_index('ix_exact_qa_vectors_embedding_hnsw', 'exact_qa_vectors', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_exact_qa_vectors_item_id', 'exact_qa_vectors', ['item_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema(整库回退到空)。"""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_exact_qa_vectors_item_id', table_name='exact_qa_vectors')
    op.drop_index('ix_exact_qa_vectors_embedding_hnsw', table_name='exact_qa_vectors', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('exact_qa_vectors')
    op.drop_index('ix_exact_qa_items_kb_status', table_name='exact_qa_items')
    op.drop_table('exact_qa_items')
    op.drop_index('ix_staging_items_kb_type', table_name='staging_items')
    op.drop_index('ix_staging_items_job_review', table_name='staging_items')
    op.drop_table('staging_items')
    op.drop_index('ix_publish_records_job_id', table_name='publish_records')
    op.drop_table('publish_records')
    op.drop_table('eval_results')
    op.drop_table('column_meta')
    op.drop_index('ix_chunks_tsv_gin', table_name='chunks', postgresql_using='gin')
    op.drop_index('ix_chunks_embedding_hnsw', table_name='chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index('ix_chunks_doc_id', table_name='chunks')
    op.drop_table('chunks')
    op.drop_index('ix_unanswered_status', table_name='unanswered_pool')
    op.drop_table('unanswered_pool')
    op.drop_index('ix_traces_message_seq', table_name='traces')
    op.drop_table('traces')
    op.drop_table('table_meta')
    op.drop_index('ix_relations_datasource_id', table_name='relations')
    op.drop_table('relations')
    op.drop_table('message_citations')
    op.drop_index('ix_ingest_jobs_status', table_name='ingest_jobs')
    op.drop_index('ix_ingest_jobs_kb_created', table_name='ingest_jobs')
    op.drop_table('ingest_jobs')
    op.drop_table('feedbacks')
    op.drop_index('ix_eval_cases_set_id', table_name='eval_cases')
    op.drop_table('eval_cases')
    op.drop_index('ix_documents_kb_id', table_name='documents')
    op.drop_table('documents')
    op.drop_table('terms')
    op.drop_index('ix_sql_examples_kb_id', table_name='sql_examples')
    op.drop_index('ix_sql_examples_embedding_hnsw', table_name='sql_examples', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('sql_examples')
    op.drop_index('ix_rules_kb_id', table_name='rules')
    op.drop_table('rules')
    op.drop_table('metrics')
    op.drop_index('ix_messages_conversation_created', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_ingest_sources_kb_id', table_name='ingest_sources')
    op.drop_table('ingest_sources')
    op.drop_index('ix_datasources_kb_id', table_name='datasources')
    op.drop_table('datasources')
    op.drop_index('ix_agent_kb_bindings_agent_id', table_name='agent_kb_bindings')
    op.drop_table('agent_kb_bindings')
    op.drop_index('ix_knowledge_bases_owner_id', table_name='knowledge_bases')
    op.drop_table('knowledge_bases')
    op.drop_index('ix_eval_runs_set_id', table_name='eval_runs')
    op.drop_table('eval_runs')
    op.drop_index('ix_conversations_user_last_message', table_name='conversations')
    op.drop_table('conversations')
    op.drop_table('users')
    op.drop_table('eval_sets')
    op.drop_table('agents')
