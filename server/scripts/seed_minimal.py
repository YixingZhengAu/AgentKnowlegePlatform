"""灌入最小演示数据:1 个用户 + 1 个默认 Agent + 3 个空知识库(三类各一)+ 绑定关系。

幂等:按唯一键 upsert 语义,重复跑不会产生重复数据(make db-reset 会调用它)。
知识内容与 Agent 提示词一律英文(D5:平台面向澳洲用户)。

用法:uv run python -m scripts.seed_minimal
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Agent, AgentKbBinding, KnowledgeBase, User
from app.models.user import DEFAULT_USERNAME

# 三类知识库:名字与描述都进 S4 路由 LLM 的 prompt,所以描述要写清"什么问题该用它"
KBS: list[dict[str, str]] = [
    {
        "name": "Product FAQ (Exact Answers)",
        "type": "exact_qa",
        "description": (
            "Curated question-answer pairs for policy and specification questions that must be "
            "answered word-for-word: warranty terms, certifications, return policy, lead times."
        ),
    },
    {
        "name": "Technical Documentation",
        "type": "document",
        "description": (
            "Installation manuals, datasheets and commissioning guides. Use for how-to and "
            "troubleshooting questions that need an answer grounded in a cited document passage."
        ),
    },
    {
        "name": "Sales Analytics",
        "type": "text2sql",
        "description": (
            "Governed semantic layer over the sales database (orders, products, regions). Use for "
            "questions about numbers: revenue, volumes, rankings, trends by state or period."
        ),
    },
]

DEFAULT_AGENT_NAME = "Clenergy Assistant"
DEFAULT_SYSTEM_PROMPT = (
    "You are the Clenergy enterprise knowledge assistant. Answer staff and partner questions "
    "about Clenergy products, documentation and sales data.\n"
    "Rules:\n"
    "- Answer only from the knowledge provided to you. Never invent specifications, prices, "
    "warranty terms or figures.\n"
    "- If the knowledge does not cover the question, say so plainly and suggest who to ask.\n"
    "- Keep answers concise and factual. Use Australian English."
)
DEFAULT_FALLBACK_REPLY = (
    "I don't have this in the knowledge base yet, so I can't answer it reliably. "
    "Please check with the product team, and this question will be logged for follow-up."
)


async def seed() -> None:
    async with SessionLocal() as session:
        # ===== 用户 =====
        user = (
            await session.execute(select(User).where(User.username == DEFAULT_USERNAME))
        ).scalar_one_or_none()
        if user is None:
            user = User(username=DEFAULT_USERNAME, display_name="Default User")
            session.add(user)
            await session.flush()
            print(f"[seed] 建用户 {DEFAULT_USERNAME}")
        else:
            print(f"[seed] 用户 {DEFAULT_USERNAME} 已存在,跳过")

        # ===== 三个空知识库 =====
        kbs: list[KnowledgeBase] = []
        for spec in KBS:
            stmt = select(KnowledgeBase).where(KnowledgeBase.name == spec["name"])
            kb = (await session.execute(stmt)).scalar_one_or_none()
            if kb is None:
                kb = KnowledgeBase(owner_id=user.id, **spec)
                session.add(kb)
                await session.flush()
                print(f"[seed] 建知识库 [{spec['type']}] {spec['name']}")
            kbs.append(kb)

        # ===== 默认 Agent =====
        agent = (
            await session.execute(select(Agent).where(Agent.name == DEFAULT_AGENT_NAME))
        ).scalar_one_or_none()
        if agent is None:
            agent = Agent(
                name=DEFAULT_AGENT_NAME,
                description="Default demo agent bound to all three knowledge bases.",
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                router_mode="rule_llm",
                fallback_reply=DEFAULT_FALLBACK_REPLY,
            )
            session.add(agent)
            await session.flush()
            print(f"[seed] 建 Agent {DEFAULT_AGENT_NAME}")

        # ===== 绑定(priority:精准 QA 最优先,这是分层治理的默认序)=====
        for priority, kb in enumerate(kbs, start=1):
            exists = (
                await session.execute(
                    select(AgentKbBinding).where(
                        AgentKbBinding.agent_id == agent.id, AgentKbBinding.kb_id == kb.id
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    AgentKbBinding(
                        agent_id=agent.id,
                        kb_id=kb.id,
                        priority=priority * 10,
                        usage_desc=kb.description,
                    )
                )
                print(f"[seed] 绑定 Agent -> {kb.name}(priority={priority * 10})")

        await session.commit()
        print("[seed] 完成")


if __name__ == "__main__":
    asyncio.run(seed())
