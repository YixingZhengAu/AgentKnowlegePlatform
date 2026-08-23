"""语义层:表/列 description 生成(B2 原样迁入)+ snapshot 落库 + 运行时语义层装配。

三块职责,都围绕同一份数据:

* **生成**(`describe_table`)—— B2 的 prompt 与四道语义校验一字未改。两种模式:
  `fill` 仅填空缺(已有 DDL 注释的列逐字保留人写的注释,AI 只补 display_name 与枚举解释),
  `rewrite` 全量重写(注释仍作上下文)。校验不过就回灌重试,最多 3 次调用。
* **落库**(`sync_schema`)—— SchemaSnapshot → `table_meta` / `column_meta` / `relations`。
  **同步只覆盖物理事实,绝不碰治理字段**:`display_name` / `description` / `is_sensitive` /
  `enabled` 是人审过的资产,重新同步一次就被冲掉的话,治理工作等于白做。
* **装配**(`load_layer`)—— 从这三张表拼出 Phase B 冻结的 semantic layer 字典。
  意图生成 / 模板生成 / 参数预填 / 运行时改写全都吃这个形状,所以它是**契约**,
  不是内部结构:字段名与嵌套跟 B2 的 `semantic_layer.json` 逐字一致。

★ `load_layer` 多带了一个 B2 产物里没有的键:每列的 `samples`。实验床阶段模板生成是
  回读 `out/schema_snapshot.json` 拿采样值的(见 B4 的 `_sample_values`);正式路径里
  同一份采样就存在 `column_meta.sample_values`,所以从语义层直接带出来,少一个数据源。
  值是同一次同步抓的同一批,prompt 内容不变。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ColumnMeta, Datasource, Relation, TableMeta
from app.services.text2sql import llm

log = get_logger(__name__)

# 数据源级业务上下文:产品里对应"数据源配置"里用户填的一句话背景,喂给所有生成 prompt。
BUSINESS_CONTEXT = (
    "Clenergy is an Australian manufacturer of solar PV mounting systems. "
    "This database covers its sales side: products (mounting kits, inverters, "
    "energy-management gear, accessories), customers, sales reps, orders with "
    "line items, and warehouse inventory with a stock-movement ledger. "
    "Amounts are in AUD."
)

#: snapshot 里 join 提示的来源词汇 → 表里的 CHECK 取值(B1 冻结的格式不改,落库时映射)
_RELATION_SOURCE = {"foreign_key": "foreign_key", "name_heuristic": "heuristic"}


DESC_SCHEMA = {
    "name": "table_semantics",
    "schema": {
        "type": "object",
        "required": ["table_description", "columns"],
        "properties": {
            "table_description": {"type": "string"},
            "columns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "display_name", "description"],
                    "properties": {
                        "name": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": "string"},
                        "enum_values": {
                            "type": ["array", "null"],
                            "items": {
                                "type": "object",
                                "required": ["value", "meaning"],
                                "properties": {
                                    "value": {"type": "string"},
                                    "meaning": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}

_SYSTEM = """You are a data analyst writing the semantic layer for a Text2SQL system.
For the given MySQL table you produce a table description and, for every column, a
business-friendly display name and description. Your text is the ONLY thing a later
AI (and business users) will see about this schema, so it must let someone who has
never looked at the data correctly understand each field.

Rules:
- Write in English only.
- table_description: 1-3 sentences; say what one row represents and what the table covers.
- display_name: a short Title Case business name, at most 4 words, no table-name prefix.
- description: 1-2 sentences per column. State units/currency, date granularity, and
  value format when the samples show them. For columns that reference another table,
  say which table and what the link means in business terms.
- For every column marked enum-like, fill enum_values explaining EVERY listed value
  (1 short sentence each, business meaning, not a restatement of the code). For all
  other columns set enum_values to null.
- Existing DDL comments (if any) are trustworthy context written by the DBA; stay
  consistent with them and never contradict them.
- Never invent facts the samples contradict. If a column's purpose is genuinely
  ambiguous, describe what the data shows rather than guessing wildly.
- Output exactly one entry per column, same names, same order as given."""


def _table(snap: dict, name: str) -> dict:
    for t in snap["tables"]:
        if t["name"] == name:
            return t
    raise KeyError(f"table not in snapshot: {name}")


def _related_context(snap: dict, name: str) -> tuple[list[dict], list[str]]:
    """返回 (涉及本表的关系, 相关表的一行式列清单)——给 prompt 的跨表上下文。"""
    rels = [r for r in snap["relations"] if name in (r["from_table"], r["to_table"])]
    others = sorted(({r["from_table"] for r in rels} | {r["to_table"] for r in rels}) - {name})
    lines = []
    for other in others:
        cols = ", ".join(c["name"] for c in _table(snap, other)["columns"])
        lines.append(f"{other}({cols})")
    return rels, lines


def _build_messages(snap: dict, name: str) -> list[dict[str, str]]:
    t = _table(snap, name)
    cols = [{
        "name": c["name"], "type": c["type"], "key": c["key"], "nullable": c["nullable"],
        "existing_comment": c["comment"] or None,
        "samples": c["samples"], "distinct_count": c["distinct_count"],
        "enum_like": c["is_enum_like"], "enum_values": c["enum_values"],
    } for c in t["columns"]]
    rels, related = _related_context(snap, name)
    user = json.dumps({
        "business_context": BUSINESS_CONTEXT,
        "table": {"name": name, "row_count": t["row_count"], "columns": cols},
        "relations_involving_this_table": rels,
        "related_tables_for_reference": related,
    }, ensure_ascii=False, indent=1)
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def _semantic_problems(t_snap: dict, result: dict) -> list[str]:
    """返回语义校验问题清单;空 = 通过。"""
    problems: list[str] = []
    want = [c["name"] for c in t_snap["columns"]]
    got = [c["name"] for c in result.get("columns", [])]
    if got != want:
        problems.append(f"columns must be exactly {want} in order, got {got}")
        return problems  # 列都对不上,后续检查无意义
    if not result.get("table_description", "").strip():
        problems.append("table_description is empty")
    enum_map = {c["name"]: c["enum_values"] for c in t_snap["columns"] if c["is_enum_like"]}
    for c in result["columns"]:
        if not c.get("display_name", "").strip() or not c.get("description", "").strip():
            problems.append(f"column {c['name']}: empty display_name or description")
        text = c.get("display_name", "") + c.get("description", "")
        if c["name"] in enum_map:
            got_vals = sorted(v["value"] for v in (c.get("enum_values") or []))
            if got_vals != sorted(enum_map[c["name"]]):
                problems.append(f"column {c['name']}: enum_values must cover exactly "
                                f"{sorted(enum_map[c['name']])}, got {got_vals}")
            for v in c.get("enum_values") or []:
                if not v.get("meaning", "").strip():
                    problems.append(f"column {c['name']}: enum value {v['value']} "
                                    f"has empty meaning")
                text += v.get("meaning", "")
        elif c.get("enum_values"):
            problems.append(f"column {c['name']}: not enum-like, enum_values must be null")
        if any("⺀" <= ch <= "鿿" for ch in text):
            problems.append(f"column {c['name']}: output must be English only (found CJK)")
    return problems


async def describe_table(snap: dict, name: str, mode: str = "fill") -> dict:
    """生成单表语义层条目。语义校验失败回灌重试,最多共 3 次调用。"""
    assert mode in ("fill", "rewrite"), mode
    t_snap = _table(snap, name)
    messages = _build_messages(snap, name)
    result: dict | None = None
    for _attempt in range(3):
        result = await llm.complete(messages, tier="main", max_tokens=4096,
                                    json_schema=DESC_SCHEMA, tag=f"desc-{name}")
        problems = _semantic_problems(t_snap, result)
        if not problems:
            break
        messages = messages + [
            {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)},
            {"role": "user", "content": "Fix these problems and return the FULL corrected JSON:\n- "
                                        + "\n- ".join(problems)},
        ]
    else:
        raise RuntimeError(f"{name}: semantic problems persist after 3 attempts: {problems}")

    # fill 模式:已有人写注释的列,description 逐字保留(AI 生成的仅用于空缺列)
    by_name = {c["name"]: c for c in t_snap["columns"]}
    for c in result["columns"]:
        src = by_name[c["name"]]
        if mode == "fill" and src["comment"]:
            c["description"] = src["comment"]
        # 语义层自带结构信息,让 B3/B4 不再回读 snapshot
        c["type"], c["key"], c["nullable"] = src["type"], src["key"], src["nullable"]
    return {"name": name, "description": result["table_description"],
            "mode": mode, "columns": result["columns"]}


# ============================================================ snapshot → 表


async def sync_schema(session: AsyncSession, ds: Datasource, snap: dict) -> dict:
    """SchemaSnapshot 落库。返回计数,供 Job 的分步日志用。

    **只覆盖物理事实**(类型、可空、键位、注释、行数、采样、distinct、是否像枚举);
    治理字段(display_name / description / is_sensitive / enabled)一律保留原值 ——
    重新同步是"库变了",不是"治理白做了"。列消失了才删它的行(元数据不该留幽灵列)。
    """
    counts = {"tables": 0, "columns": 0, "relations": 0, "dropped_columns": 0}
    existing_tables = {
        (t.schema_name, t.table_name): t
        for t in (await session.scalars(
            select(TableMeta).where(TableMeta.datasource_id == ds.id))).all()
    }
    schema = snap["database"]

    for t in snap["tables"]:
        tm = existing_tables.get((schema, t["name"]))
        if tm is None:
            tm = TableMeta(datasource_id=ds.id, schema_name=schema, table_name=t["name"])
            session.add(tm)
            await session.flush()
        tm.physical_comment = t["comment"] or None
        tm.row_count_estimate = t["row_count"]
        counts["tables"] += 1

        existing_cols = {
            c.column_name: c
            for c in (await session.scalars(
                select(ColumnMeta).where(ColumnMeta.table_meta_id == tm.id))).all()
        }
        seen: set[str] = set()
        for i, c in enumerate(t["columns"]):
            seen.add(c["name"])
            cm = existing_cols.get(c["name"])
            if cm is None:
                cm = ColumnMeta(table_meta_id=tm.id, column_name=c["name"])
                session.add(cm)
            cm.ordinal = i
            cm.data_type = c["type"]
            cm.is_nullable = bool(c["nullable"])
            cm.key_flag = c["key"]
            cm.physical_comment = c["comment"] or None
            cm.distinct_count = c["distinct_count"]
            cm.is_enum_like = bool(c["is_enum_like"])
            cm.sample_values = c["samples"]
            # enum_values 在这里只放"值",含义由 description 生成阶段补成 {value, meaning}。
            # 已经有含义的不覆盖:那是人审过的文字
            if c["is_enum_like"]:
                have = {e["value"] for e in (cm.enum_values or []) if isinstance(e, dict)}
                if set(c["enum_values"] or []) != have:
                    cm.enum_values = [{"value": v, "meaning": ""} for v in c["enum_values"]]
            else:
                cm.enum_values = None
            counts["columns"] += 1
        for name, cm in existing_cols.items():
            if name not in seen:
                await session.delete(cm)
                counts["dropped_columns"] += 1

    # join 提示整批重建:它是纯派生数据(FK + 命名启发),没有人工编辑的字段
    await session.execute(delete(Relation).where(Relation.datasource_id == ds.id))
    for r in snap["relations"]:
        session.add(Relation(
            datasource_id=ds.id,
            from_table=r["from_table"], from_column=r["from_column"],
            to_table=r["to_table"], to_column=r["to_column"],
            relation_type="many_to_one",
            source=_RELATION_SOURCE[r["source"]],
        ))
        counts["relations"] += 1

    ds.last_synced_at = datetime.now(UTC)
    log.info("text2sql_schema_synced", datasource=str(ds.id), **counts)
    return counts


async def save_descriptions(session: AsyncSession, tm: TableMeta, entry: dict) -> int:
    """把一张表的 description 生成结果写回治理字段。返回写了几列。"""
    tm.description = entry["description"]
    by_name = {c["name"]: c for c in entry["columns"]}
    cols = (await session.scalars(
        select(ColumnMeta).where(ColumnMeta.table_meta_id == tm.id))).all()
    n = 0
    for cm in cols:
        got = by_name.get(cm.column_name)
        if got is None:
            continue
        cm.display_name = got["display_name"]
        cm.description = got["description"]
        if got.get("enum_values"):
            cm.enum_values = [{"value": e["value"], "meaning": e["meaning"]}
                              for e in got["enum_values"]]
        n += 1
    return n


# ============================================================ 表 → 语义层字典


async def load_layer(session: AsyncSession, datasource_id: uuid.UUID,
                     *, enabled_only: bool = True) -> dict:
    """三张表 → Phase B 冻结的 semantic layer 形状(生成期与运行时的唯一供料)。

    `enabled_only` 是治理开关的落地:停用的表/列**不出现在语义层里**,于是既不会被
    模板生成看见,也过不了执行闸的白名单 —— 一个开关同时管住两端。
    """
    ds = await session.get(Datasource, datasource_id)
    if ds is None:
        raise KeyError(f"datasource {datasource_id} not found")

    t_stmt = select(TableMeta).where(TableMeta.datasource_id == datasource_id)
    if enabled_only:
        t_stmt = t_stmt.where(TableMeta.enabled.is_(True))
    tables_rows = (await session.scalars(t_stmt.order_by(TableMeta.table_name))).all()

    tables: list[dict] = []
    for tm in tables_rows:
        c_stmt = select(ColumnMeta).where(ColumnMeta.table_meta_id == tm.id)
        if enabled_only:
            c_stmt = c_stmt.where(ColumnMeta.enabled.is_(True))
        cols = (await session.scalars(c_stmt.order_by(ColumnMeta.ordinal))).all()
        tables.append({
            "name": tm.table_name,
            "description": tm.description or "",
            "mode": "fill",
            "columns": [{
                "name": cm.column_name,
                "display_name": cm.display_name or "",
                "description": cm.description or "",
                "enum_values": cm.enum_values or None,
                "type": cm.data_type or "",
                "key": cm.key_flag,
                "nullable": bool(cm.is_nullable),
                # B4 的 sample_values 从这里取(实验床是回读 snapshot 文件)
                "samples": cm.sample_values or [],
                "is_sensitive": bool(cm.is_sensitive),
            } for cm in cols],
        })

    names = {t["name"] for t in tables}
    rels = (await session.scalars(
        select(Relation).where(Relation.datasource_id == datasource_id))).all()
    return {
        "database": ds.name,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tables": tables,
        "relations": [{
            "from_table": r.from_table, "from_column": r.from_column,
            "to_table": r.to_table, "to_column": r.to_column,
            # 落库时映射过一次,这里映回 B1 的词汇,让语义层与实验床产物逐字可比
            "source": "name_heuristic" if r.source == "heuristic" else r.source,
        } for r in rels if r.from_table in names and r.to_table in names],
    }


def layer_json(layer: dict) -> str:
    """给冒烟脚本对比用:稳定序列化(键序固定)。"""
    return json.dumps(layer, ensure_ascii=False, sort_keys=True, indent=1)


def sensitive_columns(layer: dict) -> set[str]:
    """`table.column` 形式的敏感列集合 —— 模板生成与执行闸都要拒绝它们。"""
    return {f"{t['name']}.{c['name']}" for t in layer["tables"] for c in t["columns"]
            if c.get("is_sensitive")}
