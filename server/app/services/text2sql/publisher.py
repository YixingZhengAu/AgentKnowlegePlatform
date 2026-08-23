"""采纳与发布 —— 意图候选(staging_items)→ 意图(sql_intents)→ 已发布(+ 索引面)。

★ **S3 的"采纳"与"发布"是两件事**,这一点和 S1 不同,值得说清:

```
候选意图 ──采纳──▶ sql_intents(status=draft)──── 在意图详情页上迭代 ────▶ 发布
  (审核台)          还没有 SQL、没有参数区          生成模板 → Run → 改 SQL      status=published
                                                → 参数区 AI 预填 → 编辑 hint     + 建索引面
                                                → 生成/编辑相似问法
```

S1 是"采纳即发布"(点一下就进检索),因为它审的是一段文本对不对。S3 审的是
**这条 SQL 能不能跑出对的数** —— 那要看真数据、要能改 SQL 再 Run 一遍,泛型审核台答不了。
所以采纳只表示"这类问题值得做成模板",发布才表示"这条模板我验收了"。

★ 发布是一个事务:写 `sql_intents` + 重建 `intent_vectors`。**向量写失败,状态就不该改** ——
否则会出现一个"已发布但检索不到"的意图,而这种半残状态在界面上完全看不出来。

★ 下线 = `status='disabled'` + 删它的索引面,正式行不物理删(它可能被
`message_citations.ref_id` 引用过,删了历史消息的引用会悬空)。与 S1 同一条纪律。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.staging import register_publisher
from app.models import Datasource, SqlIntent, StagingItem
from app.services.text2sql import indexer

log = get_logger(__name__)

ITEM_TYPE = "sql_intent"


def _now() -> datetime:
    return datetime.now(UTC)


async def next_code(session: AsyncSession, kb_id: uuid.UUID) -> str:
    """下一个人可读 code:i01, i02, ...(kb 内唯一,见 `uq_sql_intents_kb_code`)。

    不用 uuid 是因为 code 会出现在 trace 面板、评审报告和评测集里 —— 那些材料是给人看的。
    """
    codes = (await session.scalars(
        select(SqlIntent.code).where(SqlIntent.kb_id == kb_id))).all()
    used = {int(c[1:]) for c in codes if c.startswith("i") and c[1:].isdigit()}
    n = 1
    while n in used:
        n += 1
    return f"i{n:02d}"


async def _adopt_one(session: AsyncSession, staging: StagingItem) -> dict:
    """一条候选 → 一条 draft 意图。**不 commit**(采纳是一个事务)。

    幂等:已采纳过的直接返回原来的 published_ref,不写第二份(前端重复点、
    批量与逐条撞在一起,都不该产生重复知识)。
    """
    if staging.published and staging.published_ref:
        return staging.published_ref

    payload = staging.payload or {}
    one_liner = (payload.get("one_liner") or "").strip()
    brief = (payload.get("brief") or "").strip()
    intent_type = payload.get("intent_type")
    tables = list(payload.get("tables") or [])
    if not one_liner or not brief or intent_type not in ("query", "stats") or not tables:
        # 生成阶段已经校验过,但人在审核台上可以改坏 —— 这里是最后一道防线
        raise ConflictError(
            "An intent needs a summary, a brief, a type (query/stats) and at least one table",
            code="sql_intent_incomplete",
        )

    datasource_id = payload.get("datasource_id")
    if datasource_id is None:
        # 一个 kb 目前只接一个演示数据源;多数据源时由生成阶段把它写进 payload
        ds = (await session.scalars(
            select(Datasource).where(Datasource.kb_id == staging.kb_id,
                                     Datasource.status == "active")
            .order_by(Datasource.created_at))).first()
        if ds is None:
            raise ConflictError(
                "This knowledge base has no active datasource to attach the intent to",
                code="datasource_missing")
        datasource_id = ds.id

    intent = SqlIntent(
        kb_id=staging.kb_id,
        datasource_id=uuid.UUID(str(datasource_id)),
        code=payload.get("code") or await next_code(session, staging.kb_id),
        intent_type=intent_type,
        bucket=payload.get("bucket"),
        one_liner=one_liner,
        brief=brief,
        tables=tables,
        status="draft",
        source_staging_id=staging.id,
    )
    session.add(intent)
    await session.flush()

    staging.published = True
    staging.published_ref = {"table": "sql_intents", "id": str(intent.id),
                             "code": intent.code, "status": intent.status}
    return staging.published_ref


@register_publisher(ITEM_TYPE)
async def publish_sql_intents(
    session: AsyncSession, items: list[StagingItem]
) -> list[dict | None]:
    """批量采纳入口(`core/staging.py::publish_job` 调它)。逐条走同一条路。

    注意它产出的是 **draft**:批量通过审核台只表示"这些意图我要",
    不表示模板已经验收过 —— 那一步在意图详情页上,一条一条来。
    """
    refs: list[dict | None] = []
    for staging in items:
        refs.append(await _adopt_one(session, staging))
    log.info("sql_intents_adopted_batch", count=len(items))
    return refs


# ---------------------------------------------------------------- 发布 / 下线


def publish_blockers(intent: SqlIntent) -> list[str]:
    """发布前的硬前置。返回空列表才允许发布。

    这些不是"建议",是**发布按钮变灰的原因**,所以每条都要能直接显示给用户看:
    一个没有 SQL 或没有参数区的意图发出去,运行时就是一条必然 execution_failed 的链路。
    """
    problems: list[str] = []
    if not (intent.sql or "").strip():
        problems.append("The intent has no SQL template yet. Generate and run one first.")
    params = intent.params or {}
    if not params.get("outputs"):
        problems.append("The parameter panel is empty. Parse the template's parameters first.")
    return problems


async def publish_intent(session: AsyncSession, intent_id: uuid.UUID) -> dict:
    """发布一个意图:校验 → status=published → 重建索引面。一个事务,调用方 commit。"""
    intent = await session.get(SqlIntent, intent_id)
    if intent is None:
        raise NotFoundError(f"Intent {intent_id} not found")
    blockers = publish_blockers(intent)
    if blockers:
        raise ConflictError(" ".join(blockers), code="sql_intent_not_publishable",
                            detail={"blockers": blockers})
    intent.status = "published"
    intent.published_at = _now()
    faces = await indexer.rebuild_intent_faces(session, intent)
    # 空路由面是 kb 级资产,和意图一起保证在位 —— 少了它,非问数问题会撞进最近的模板
    non_data = await indexer.rebuild_non_data_faces(session, intent.kb_id)
    log.info("sql_intent_published", intent=intent.code, faces=faces, non_data_faces=non_data)
    return {"intent_id": str(intent.id), "code": intent.code,
            "faces": faces, "non_data_faces": non_data}


async def disable_intent(session: AsyncSession, intent_id: uuid.UUID) -> dict:
    """下线一个意图:status=disabled + 删索引面。正式行留着(历史引用不能悬空)。"""
    intent = await session.get(SqlIntent, intent_id)
    if intent is None:
        raise NotFoundError(f"Intent {intent_id} not found")
    intent.status = "disabled"
    await indexer.drop_intent_faces(session, intent.id)
    log.info("sql_intent_disabled", intent=intent.code)
    return {"intent_id": str(intent.id), "code": intent.code, "status": intent.status}
