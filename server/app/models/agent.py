"""Agent 域:agents + agent_kb_bindings(Agent 绑哪些知识库、各自的检索参数)。"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, REAL
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, enum_check

ROUTER_MODES = ("rule_llm", "llm_only")
AGENT_STATUSES = ("active", "archived")


class Agent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (
        enum_check("router_mode", ROUTER_MODES, "ck_agents_router_mode"),
        enum_check("status", AGENT_STATUSES, "ck_agents_status"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # rule_llm = 精准 QA 规则前置 + LLM 路由其余部分
    router_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="rule_llm")
    # {"temperature":0.3} 等覆盖项;tier->型号映射仍在 env,不写型号名
    model_cfg: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # 无证据时的兜底话术
    fallback_reply: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class AgentKbBinding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_kb_bindings"
    __table_args__ = (
        UniqueConstraint("agent_id", "kb_id", name="uq_agent_kb_bindings"),
        Index("ix_agent_kb_bindings_agent_id", "agent_id"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    # 越小越优先
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # NULL = 用该知识类型的默认值
    top_k: Mapped[int | None] = mapped_column(Integer)
    threshold: Mapped[float | None] = mapped_column(REAL)
    # 给路由 LLM 看的"什么问题该用这个库"
    usage_desc: Mapped[str | None] = mapped_column(Text)
