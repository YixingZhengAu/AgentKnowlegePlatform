"""运行时装配:把 chat 的一次提问接到 B8 的 `pipeline.answer()` 上。

★ **为什么要这一层**:`pipeline.py` 是刻意无 I/O 的(索引 / 发布包 / 语义层 / 连接全从外面
  传入),那是它能被评测集反复重跑的前提。总得有人去库里把这四样东西装出来 ——
  装配放在这里,`core/chat.py` 那边就只剩"调一次、把结果摊成事件",不掺任何本域知识。

装出来的四样东西:

| 东西 | 从哪来 | 注意 |
| --- | --- | --- |
| `index` | `intent_vectors`(含空路由面) | 少了它,非问数问题会撞进最近的模板 |
| `packages` | 已发布 `sql_intents` 的 sql + params | 形状与 B5 的模板包逐字一致 |
| `layer` | 语义层三张表(只含 enabled 的表列) | 执行闸的白名单就是它 |
| `conn` | `datasources.dsn_enc` 解密 | 明文只在进程内存活 |

★ **一个 kb 一个数据源**:S3 的边界。索引里万一混进了别的数据源的意图(多数据源是
  未实现的场景),那些面会被剔掉并记一条 warning —— 宁可少答一类问题,
  也不能拿 A 库的语义层去执行 B 库的模板。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import AgentKbBinding, Datasource, KnowledgeBase, SqlIntent
from app.providers.base import LLMResult
from app.services.text2sql import llm, semantic
from app.services.text2sql import pipeline as pl
from app.services.text2sql import retrieve as rt
from app.services.text2sql.bizdb import BizConn, decrypt_dsn, parse_dsn

log = get_logger(__name__)


@dataclass(slots=True)
class Text2SqlRuntime:
    """一次问答要用到的全部输入。装一次用一次 —— 不缓存。

    不缓存是有意的:索引与模板会被治理台随时改(发布、下线、改问法),
    缓存就得处理失效,而这条链路的装载成本是几条按索引走的查询,不值得为它引入一致性问题。
    """

    kb_id: uuid.UUID
    datasource_id: uuid.UUID
    index: list[dict]
    packages: dict[str, dict]
    layer: dict
    conn: BizConn
    #: code → 意图行 id(引用要指向正式行,而 code 只是给人看的)
    intent_ids: dict[str, uuid.UUID] = field(default_factory=dict)


async def agent_text2sql_kb_ids(session: AsyncSession, agent_id: uuid.UUID) -> list[uuid.UUID]:
    """这个 Agent 绑了哪些 text2sql 知识库(只算 enabled 的绑定)。

    与 S1 同一条纪律:按绑定过滤,而不是"库里所有已发布意图都能被任何 Agent 命中" ——
    否则多 Agent 演示时会互相串味,S4 的路由也无从谈起。
    """
    rows = (
        await session.execute(
            select(AgentKbBinding.kb_id)
            .join(KnowledgeBase, KnowledgeBase.id == AgentKbBinding.kb_id)
            .where(
                AgentKbBinding.agent_id == agent_id,
                AgentKbBinding.enabled.is_(True),
                KnowledgeBase.type == "text2sql",
                KnowledgeBase.status == "active",
            )
        )
    ).all()
    return [r[0] for r in rows]


async def load_runtime(
    session: AsyncSession, kb_ids: list[uuid.UUID]
) -> Text2SqlRuntime | None:
    """装出一次问答要的四样东西。**没有可用知识就返回 None**(不是抛错)。

    "这个 Agent 没绑问数库"和"绑了但一条模板都没发布"都是正常状态,
    调用方据此跳过整个 stage —— 零 LLM 成本。
    """
    for kb_id in kb_ids:
        intents = (
            await session.scalars(
                select(SqlIntent)
                .where(SqlIntent.kb_id == kb_id, SqlIntent.status == "published")
                .order_by(SqlIntent.code)
            )
        ).all()
        if not intents:
            continue
        index = await rt.load_index(session, kb_id)
        if not index:
            # 有已发布意图却没有索引面 = 半残状态(发布事务应该保证不出现),记下来别静默
            log.warning("text2sql_index_empty", kb_id=str(kb_id), intents=len(intents))
            continue

        ds_id = intents[0].datasource_id
        packages: dict[str, dict] = {}
        skipped: list[str] = []
        for it in intents:
            if it.datasource_id != ds_id:
                skipped.append(it.code)
                continue
            packages[it.code] = {
                "intent": {
                    "intent_id": it.code, "type": it.intent_type, "bucket": it.bucket,
                    "one_liner": it.one_liner, "brief": it.brief,
                    "tables": list(it.tables or []),
                },
                "sql": it.sql,
                "params": it.params,
            }
        if skipped:
            log.warning("text2sql_multi_datasource_skipped", kb_id=str(kb_id), codes=skipped)
            index = [
                f for f in index
                if f["intent_id"] in packages or f["intent_id"] == rt.NON_DATA_INTENT
            ]

        ds = await session.get(Datasource, ds_id)
        if ds is None or not ds.readonly_confirmed:
            log.warning("text2sql_datasource_unusable", kb_id=str(kb_id),
                        datasource_id=str(ds_id))
            continue
        return Text2SqlRuntime(
            kb_id=kb_id,
            datasource_id=ds_id,
            index=index,
            packages=packages,
            layer=await semantic.load_layer(session, ds_id),
            conn=parse_dsn(decrypt_dsn(ds.dsn_enc)),
            intent_ids={it.code: it.id for it in intents},
        )
    return None


async def answer(question: str, ctx: Text2SqlRuntime) -> tuple[dict, list[LLMResult]]:
    """跑一次完整链路。返回 (结果包, 这次花掉的 LLM 调用)。

    第二个返回值是给 trace 记账用的:B8 的模块只接收 dict(评审过的调用行不改),
    所以用量走 `llm.collect_usage()` 的收集桶。非问数问题的桶是空的 ——
    **那正是"检索层拒答零 LLM 成本"这句话的证据**,不是遗漏。
    """
    with llm.collect_usage() as usages:
        result = await pl.answer(question, ctx.index, ctx.packages, ctx.layer, ctx.conn)
    return result, usages


def citations(result: dict, ctx: Text2SqlRuntime) -> list[dict]:
    """命中并执行成功 → 一条 `sql` 引用。**强制引用**:数字必须能点回它是怎么算出来的。

    `snippet` 放最终 SQL(前端可展开 + 复制),结果表格与行数进 `extra` ——
    前端要能不再发一次请求就把表格画出来。
    """
    if result["outcome"] != "executed" or not result.get("execution"):
        return []
    exe = result["execution"]
    code = result["intent_id"]
    return [
        {
            "seq": 1,
            "citation_type": "sql",
            "ref_id": str(ctx.intent_ids[code]) if code in ctx.intent_ids else None,
            "snippet": exe["sql_executed"],
            "extra": {
                "intent_code": code,
                "intent_summary": result.get("intent_summary"),
                "score": round(result["retrieval"]["top1_score"], 4),
                "needs_confirmation": result["needs_confirmation"],
                "cols": exe["cols"],
                "rows": [[_jsonable(v) for v in row] for row in exe["sample"]],
                "rowcount": exe["rowcount"],
                "flags": exe["flags"],
            },
        }
    ]


def _jsonable(v: object) -> object:
    """Decimal / date 直接进 JSON 会炸(引用要落库成 jsonb),统一落成 str。"""
    return v if v is None or isinstance(v, (bool, int, float, str)) else str(v)


#: 埋点形状的唯一出处在 `pipeline.trace_events()`;这里只是让 `core/chat.py` 不必再 import 它
trace_events = pl.trace_events
#: 两句面向用户的拒答文案也从这里出去(它们有评测集断言,不许在别处再写一份)
NON_DATA_REPLY = pl.NON_DATA_REPLY
OUT_OF_TEMPLATE_REPLY = pl.OUT_OF_TEMPLATE_REPLY
