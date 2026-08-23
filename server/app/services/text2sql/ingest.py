"""S3 的三个摄取 Job:`t2s_sync_schema`(同步 schema)/ `t2s_describe`(批量写描述)/
`t2s_intents`(批量提意图)。

★ **为什么是三个 Job 而不是一条流水线**:中间夹着两道人工关,而且三件事的重跑成本天差地别。

```
接数据源 ─▶ t2s_sync_schema ─▶ Schema 治理页 ─▶ t2s_describe ─▶ 人改描述 ─▶ t2s_intents ─▶ 审核台
            introspect/persist  勾选启用的表列   generate/save   (就地编辑)  generate/judge/stage
            零 LLM,秒级         ↑人工            每表一次 LLM               终态 review(等采纳)
            终态 published                       终态 published
```

同步是免费的,随时可重跑;写描述每表一次 gpt-5,重跑要重花钱;提意图要在**已经治理过的**
描述上做,提前跑等于拿空描述喂模型。混成一个 Job 的代价是:错一步就得从头重跑,
而且没法在中间停下来等人勾选启用哪些表。

★ 三个 Job 的终态只有 `t2s_intents` 是 `review`(它产出待采纳的候选);前两个直接写治理
字段,没有待审条目,所以是 `published`。这不是偷懒:它们的审核界面是 Schema 治理页
本身(就地编辑),不是泛型审核台 —— 理由见 DB-DESIGN §8。
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.jobs import JobRunContext, JobRunner, JobStepDef, register_job
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models import Datasource, SqlIntent, StagingItem, TableMeta
from app.services.text2sql import bizdb, introspect, semantic
from app.services.text2sql import intents as intent_gen

log = get_logger(__name__)


class _DatasourceJob(JobRunner):
    """三个 Job 共用的准备工作:从 params 取 datasource_id,顺手把连接要素解出来。

    连接串只在进程内存活(解密后就丢在 ctx.scratch 里),不写回任何地方 ——
    Job 的 `params` 会落库并出现在接口响应里,明文口令绝不能进它。
    """

    async def prepare(self, ctx: JobRunContext) -> None:
        raw = ctx.params.get("datasource_id")
        if not raw:
            raise RuntimeError("params 缺 datasource_id")
        ds_id = uuid.UUID(str(raw))
        async with SessionLocal() as session:
            ds = await session.get(Datasource, ds_id)
            if ds is None:
                raise RuntimeError(f"Datasource {ds_id} not found")
            ctx.scratch["datasource_id"] = ds_id
            ctx.scratch["conn"] = bizdb.parse_dsn(bizdb.decrypt_dsn(ds.dsn_enc))


@register_job
class SyncSchemaJob(_DatasourceJob):
    """同步库表结构。零 LLM,所以它可以随便重跑 —— 也应该:库变了就重跑一次。"""

    job_type = "t2s_sync_schema"
    steps = [
        JobStepDef("introspect", "Read the database schema"),
        JobStepDef("persist", "Store tables, columns and joins"),
    ]
    terminal_status = "published"

    async def step_introspect(self, ctx: JobRunContext) -> str:
        # introspection 是几十条小查询,整段挪到线程,不逐条 await
        snap = await asyncio.to_thread(introspect.build_snapshot, ctx.scratch["conn"])
        ctx.scratch["snapshot"] = snap
        enum_cols = sum(1 for t in snap["tables"] for c in t["columns"] if c["is_enum_like"])
        return (f"{len(snap['tables'])} tables, "
                f"{sum(len(t['columns']) for t in snap['tables'])} columns, "
                f"{enum_cols} enum-like columns, {len(snap['relations'])} joins")

    async def step_persist(self, ctx: JobRunContext) -> str:
        async with SessionLocal() as session:
            ds = await session.get(Datasource, ctx.scratch["datasource_id"])
            counts = await semantic.sync_schema(session, ds, ctx.scratch["snapshot"])
            await session.commit()
        return (f"{counts['tables']} tables / {counts['columns']} columns / "
                f"{counts['relations']} joins stored"
                + (f"; {counts['dropped_columns']} columns gone from the source"
                   if counts["dropped_columns"] else ""))


@register_job
class DescribeSchemaJob(_DatasourceJob):
    """批量生成表/列描述(语义层的正文)。每张启用的表一次 gpt-5 调用。

    `mode` 走 params:`fill`(默认,只填空缺,人写的 DDL 注释逐字保留)或 `rewrite`(全量重写)。
    **治理字段只有这个 Job 和人会写**,schema 同步永远不碰它们。
    """

    job_type = "t2s_describe"
    steps = [
        JobStepDef("generate", "Write table and column descriptions"),
        JobStepDef("save", "Save the semantic layer"),
    ]
    terminal_status = "published"

    async def step_generate(self, ctx: JobRunContext) -> str:
        mode = ctx.params.get("mode", "fill")
        snap = await asyncio.to_thread(introspect.build_snapshot, ctx.scratch["conn"])
        ctx.scratch["snapshot"] = snap
        async with SessionLocal() as session:
            wanted = list((await session.scalars(
                select(TableMeta.table_name).where(
                    TableMeta.datasource_id == ctx.scratch["datasource_id"],
                    TableMeta.enabled.is_(True))
                .order_by(TableMeta.table_name))).all())
        only = ctx.params.get("tables")
        if only:
            wanted = [t for t in wanted if t in set(only)]
        if not wanted:
            raise RuntimeError("no enabled table to describe — sync the schema first")
        # 逐表串行:一次是 gpt-5 的几千 token,并发起来只会更容易撞限流,
        # 而这个 Job 本来就是"提交完可以离开页面"的形态
        entries = []
        for name in wanted:
            entries.append(await semantic.describe_table(snap, name, mode=mode))
        ctx.scratch["entries"] = entries
        return f"{len(entries)} tables described (mode={mode})"

    async def step_save(self, ctx: JobRunContext) -> str:
        written = 0
        async with SessionLocal() as session:
            for entry in ctx.scratch["entries"]:
                tm = (await session.scalars(
                    select(TableMeta).where(
                        TableMeta.datasource_id == ctx.scratch["datasource_id"],
                        TableMeta.table_name == entry["name"]))).first()
                if tm is None:
                    continue
                written += await semantic.save_descriptions(session, tm, entry)
            await session.commit()
        return (f"{len(ctx.scratch['entries'])} table descriptions + "
                f"{written} column descriptions saved")


@register_job
class GenerateIntentsJob(_DatasourceJob):
    """批量提意图候选 → 审核台。终态 `review`,等人采纳。

    `judge` 那一步是**生成完自己盲判一遍**:只把 brief 喂给 light 模型(不给 type、
    不给 `Query:`/`Stats:` 前缀),让它判"这题的 SQL 需不需要 GROUP BY",再和声明的 type 比。
    文案与分型不符会在这里被抓出来 —— 这类错在后面 SQL 模板生成时才炸,那时已经花过钱了。
    盲判不一致**不拦**,只写进候选的 payload 让人看见:判官本身也会错,
    它的价值是"提醒人看这一条",不是"替人否决"。
    """

    job_type = "t2s_intents"
    steps = [
        JobStepDef("generate", "Draft question intents"),
        JobStepDef("judge", "Cross-check each intent's type"),
        JobStepDef("stage", "Write candidates for review"),
    ]

    async def step_generate(self, ctx: JobRunContext) -> str:
        n = int(ctx.params.get("count", 10))
        async with SessionLocal() as session:
            layer = await semantic.load_layer(session, ctx.scratch["datasource_id"])
            # 追加生成:把已有意图的 one-liner 喂回 prompt 要求避重(在源头防重复,
            # 比事后判重便宜 —— 判重只能告诉你钱已经花了)
            avoid = list((await session.scalars(
                select(SqlIntent.one_liner).where(SqlIntent.kb_id == ctx.kb_id))).all())
        tables = ctx.params.get("tables") or [t["name"] for t in layer["tables"]]
        if not [t for t in layer["tables"] if t["name"] in set(tables)]:
            raise RuntimeError("the semantic layer is empty — sync and describe the schema first")
        ctx.scratch["layer"] = layer
        drafted = await intent_gen.generate_intents(layer, tables, n, avoid)
        # 生成阶段不给 id,盲判和落库都要引用它 —— 给一个批内序号
        for i, it in enumerate(drafted, start=1):
            it["id"] = f"c{i:02d}"
        ctx.scratch["intents"] = drafted
        return f"{len(drafted)} intents drafted over {len(tables)} tables"

    async def step_judge(self, ctx: JobRunContext) -> str:
        verdicts = await intent_gen.judge_group_by(ctx.scratch["intents"])
        mismatched = []
        for it in ctx.scratch["intents"]:
            needs_gb = verdicts.get(it["id"])
            it["type_agrees_with_judge"] = (
                None if needs_gb is None else needs_gb == (it["type"] == "stats"))
            if it["type_agrees_with_judge"] is False:
                mismatched.append(it["id"])
        return (f"{len(ctx.scratch['intents']) - len(mismatched)} agree with the blind judge"
                + (f"; flagged for review: {mismatched}" if mismatched else ""))

    async def step_stage(self, ctx: JobRunContext) -> str:
        async with SessionLocal() as session:
            for it in ctx.scratch["intents"]:
                session.add(StagingItem(
                    job_id=ctx.job_id,
                    kb_id=ctx.kb_id,
                    item_type="sql_intent",
                    payload={
                        "intent_type": it["type"],
                        "bucket": it["bucket"],
                        "one_liner": it["one_liner"],
                        "brief": it["brief"],
                        "tables": it["tables"],
                        "datasource_id": str(ctx.scratch["datasource_id"]),
                    },
                    # 盲判分歧不是"置信度低",但它是人最该先看的那几条,所以借这一列排序
                    confidence=None if it["type_agrees_with_judge"] is None
                    else (1.0 if it["type_agrees_with_judge"] else 0.5),
                ))
            await session.commit()
        # 审核台入口那块摆的就是这个数(共享 <JobProgress> 读 stats.staged);
        # 不写它,界面会说"0 items are waiting for review"而底下明明有几条
        ctx.scratch["stats"] = {"staged": len(ctx.scratch["intents"])}
        return f"{len(ctx.scratch['intents'])} candidates awaiting review"
