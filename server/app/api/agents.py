"""Agent 只读接口(Step 6 前端列表页 + Agent 详情的数据源)。"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.errors import NotFoundError
from app.models import Agent, AgentKbBinding, KnowledgeBase
from app.schemas.agent import AgentDetailOut, AgentKbBindingOut, AgentOut
from app.schemas.common import ListResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=ListResponse[AgentOut])
async def list_agents(session: SessionDep) -> ListResponse:
    rows = (await session.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    items = [AgentOut.model_validate(r) for r in rows]
    return ListResponse[AgentOut](items=items, total=len(items))


@router.get("/{agent_id}", response_model=AgentDetailOut)
async def get_agent(agent_id: uuid.UUID, session: SessionDep) -> AgentDetailOut:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise NotFoundError(f"Agent {agent_id} not found")

    # 绑定要带上 KB 的名字和类型,前端才能画出"这个 Agent 挂了哪几类知识"
    rows = (
        await session.execute(
            select(AgentKbBinding, KnowledgeBase)
            .join(KnowledgeBase, KnowledgeBase.id == AgentKbBinding.kb_id)
            .where(AgentKbBinding.agent_id == agent.id)
            .order_by(AgentKbBinding.priority)
        )
    ).all()
    bindings = [
        AgentKbBindingOut(
            id=b.id,
            kb_id=kb.id,
            kb_name=kb.name,
            kb_type=kb.type,
            priority=b.priority,
            enabled=b.enabled,
            top_k=b.top_k,
            threshold=b.threshold,
            usage_desc=b.usage_desc,
        )
        for b, kb in rows
    ]
    # 先按 ORM 取标量字段,再拼上 bindings(bindings 不是 Agent 上的属性)
    return AgentDetailOut(
        **AgentOut.model_validate(agent).model_dump(),
        system_prompt=agent.system_prompt,
        fallback_reply=agent.fallback_reply,
        model_cfg=agent.model_cfg,
        bindings=bindings,
    )
