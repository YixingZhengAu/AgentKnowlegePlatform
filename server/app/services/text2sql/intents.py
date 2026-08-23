"""意图候选生成(B3 原样迁入):所选表集合 → N 条意图(先定型再写文案)。

铁律(与 S3 需求一一对应):
  * 只有两种 type:query(SQL 无 GROUP BY)/ stats(SQL 必有 GROUP BY);
  * one_liner 强制 "Query: " / "Stats: " 纯文本前缀领跑,且与 type 一致;
  * 覆盖桶固定五个,桶与 type 有确定映射(*_query→query,*_stats→stats),多一道免费一致性校验;
  * 追加生成(--append)把已有 one-liner 喂回 prompt 要求避重。
自测用 gpt-5-mini 盲判:只看 brief(剥掉前缀、不给 type),判"SQL 是否需要 GROUP BY",
与 type 比对 —— 文案与分型不符会被抓出来。两个 judge 函数留在正式代码里,是因为
"生成完先自己盲判一遍"是意图批量生成 Job 的一步,不是只在实验床里跑的自测。
"""

from __future__ import annotations

import json

from app.services.text2sql import llm
from app.services.text2sql.semantic import BUSINESS_CONTEXT

BUCKETS = {
    "single_table_query": "query",
    "multi_table_query": "query",
    "time_stats": "stats",
    "category_stats": "stats",
    "ranking_stats": "stats",
}

INTENT_SCHEMA = {
    "name": "intent_candidates",
    "schema": {
        "type": "object",
        "required": ["intents"],
        "properties": {
            "intents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["type", "bucket", "one_liner", "brief", "tables"],
                    "properties": {
                        "type": {"type": "string", "enum": ["query", "stats"]},
                        "bucket": {"type": "string", "enum": list(BUCKETS)},
                        "one_liner": {"type": "string"},
                        "brief": {"type": "string"},
                        "tables": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    },
}

GEN_SYSTEM = """You are helping a business user of a Text2SQL platform define "question intents"
over the database tables they selected. Each intent is a reusable question pattern that will
later become exactly one SQL template, so every intent must be answerable by a single SELECT.

There are exactly two types. Decide the type FIRST, then write the wording:
- "query": returns detail rows; the SQL would have NO GROUP BY. Filtering, sorting, or
  top-N by a stored column value are still query.
- "stats": aggregates rows into groups; the SQL REQUIRES GROUP BY (counts / sums / averages
  per month, per category, per rep..., or rankings by an aggregated measure).

Typing examples:
- "Look up recent orders of a customer" -> query
- "Top 10 products by total sales amount" -> stats (SUM aggregated per product)
- "Show the stock movement history of a product" -> query
- "Monthly order count trend" -> stats
- "List products priced above 1000 AUD" -> query (sorting/filtering only)

Each intent must have:
- type: "query" | "stats"
- bucket: coverage bucket, one of single_table_query / multi_table_query (type must be query)
  and time_stats / category_stats / ranking_stats (type must be stats). Spread intents across
  buckets; never leave a bucket empty when the requested count allows covering all.
- one_liner: MUST start with the keyword "Query: " or "Stats: " matching the type, followed
  by one short sentence a user would instantly recognize in a picker list.
- brief: 2-3 sentences stating exactly what the question returns, which conditions a user would
  typically vary when asking it (time range, status, a specific product/customer/rep, ...), and
  for stats the grouping dimension(s) and the aggregation measure with its business meaning
  (e.g. revenue = sum of order line amounts excluding cancelled orders). The brief later drives
  SQL generation, so be precise; never mention SQL keywords, describe the business meaning.
- tables: the minimal subset of the SELECTED tables the question needs (join tables included).

Rules:
- Use ONLY the selected tables and their listed columns; if a natural question would need an
  unselected table, do not propose it.
- Questions must be ones an Australian sales/operations manager would genuinely ask.
- No two intents may be near-duplicates of each other or of the AVOID list (if given).
- English only."""


def _layer_subset(layer: dict, table_names: list[str]) -> dict:
    tables = [t for t in layer["tables"] if t["name"] in table_names]
    missing = set(table_names) - {t["name"] for t in tables}
    if missing:
        raise KeyError(f"tables not in semantic layer: {sorted(missing)}")
    rels = [r for r in layer["relations"]
            if r["from_table"] in table_names and r["to_table"] in table_names]
    slim = [{"name": t["name"], "description": t["description"],
             "columns": [{"name": c["name"], "display_name": c["display_name"],
                          "description": c["description"], "type": c["type"],
                          "enum_values": c.get("enum_values")} for c in t["columns"]]}
            for t in tables]
    return {"tables": slim, "relations": [
        {"from": f"{r['from_table']}.{r['from_column']}", "to": f"{r['to_table']}.{r['to_column']}"}
        for r in rels]}


def _problems(result: dict, table_names: list[str], n: int, avoid: list[str]) -> list[str]:
    probs: list[str] = []
    intents = result.get("intents", [])
    if len(intents) != n:
        probs.append(f"must return exactly {n} intents, got {len(intents)}")
    for i, it in enumerate(intents):
        tag = f"intent #{i + 1}"
        prefix = "Query: " if it["type"] == "query" else "Stats: "
        if not it["one_liner"].startswith(prefix):
            probs.append(f"{tag}: one_liner must start with '{prefix}' (type={it['type']})")
        if BUCKETS.get(it["bucket"]) != it["type"]:
            probs.append(f"{tag}: bucket {it['bucket']} conflicts with type {it['type']}")
        bad = set(it["tables"]) - set(table_names)
        if bad or not it["tables"]:
            probs.append(f"{tag}: tables must be a non-empty subset of "
                         f"{table_names}, got {it['tables']}")
        if not it["brief"].strip() or len(it["brief"]) < 40:
            probs.append(f"{tag}: brief too short — 2-3 precise sentences required")
        text = it["one_liner"] + it["brief"]
        if any("⺀" <= ch <= "鿿" for ch in text):
            probs.append(f"{tag}: English only (found CJK)")
        if it["one_liner"] in avoid:
            probs.append(f"{tag}: duplicates an AVOID-list one_liner verbatim")
    return probs


def build_gen_messages(layer: dict, table_names: list[str], n: int,
                       avoid: list[str]) -> list[dict[str, str]]:
    """组装一次生成调用的完整输入(公开:评审报告原样展示它)。"""
    user = json.dumps({
        "business_context": BUSINESS_CONTEXT,
        "selected_tables": _layer_subset(layer, table_names),
        "how_many_intents": n,
        "avoid_duplicating_these_existing_intents": avoid or None,
    }, ensure_ascii=False, indent=1)
    return [{"role": "system", "content": GEN_SYSTEM}, {"role": "user", "content": user}]


async def generate_intents(layer: dict, table_names: list[str], n: int,
                           avoid: list[str] | None = None) -> list[dict]:
    """生成 n 条意图。结构校验失败回灌重试,最多共 3 次调用。"""
    avoid = avoid or []
    messages = build_gen_messages(layer, table_names, n, avoid)
    for _ in range(3):
        result = await llm.complete(messages, tier="main", max_tokens=6144,
                                    json_schema=INTENT_SCHEMA, tag="intent-gen")
        probs = _problems(result, table_names, n, avoid)
        if not probs:
            return result["intents"]
        messages = messages + [
            {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)},
            {"role": "user", "content": "Fix these problems and return the FULL corrected JSON:\n- "
                                        + "\n- ".join(probs)},
        ]
    raise RuntimeError(f"intent generation: problems persist after 3 attempts: {probs}")


# ---------------- LLM-judge 盲判(自测用,light tier) ----------------

JUDGE_GB_SYSTEM = (
    "For each item, decide from the question brief alone whether answering it in SQL "
    "requires GROUP BY (aggregating rows per group: per month / per category / per "
    "entity, or ranking by an aggregated measure). Detail listings, filters, sorting "
    "and top-N by a stored column do NOT need GROUP BY. Return a verdict per id.")

_JUDGE_GB_SCHEMA = {
    "name": "groupby_verdicts",
    "schema": {"type": "object", "required": ["verdicts"], "properties": {
        "verdicts": {"type": "array", "items": {"type": "object",
            "required": ["id", "needs_group_by"], "properties": {
                "id": {"type": "string"}, "needs_group_by": {"type": "boolean"}}}}}},
}


async def judge_group_by(intents: list[dict]) -> dict[str, bool]:
    """盲判:只给 brief(不给 type/前缀/桶),判 SQL 是否需要 GROUP BY。"""
    items = [{"id": it["id"], "question_brief": it["brief"]} for it in intents]
    messages = [
        {"role": "system", "content": JUDGE_GB_SYSTEM},
        {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
    ]
    result = await llm.complete(messages, tier="light", max_tokens=2048,
                                json_schema=_JUDGE_GB_SCHEMA, tag="intent-judge-gb")
    return {v["id"]: v["needs_group_by"] for v in result["verdicts"]}


JUDGE_DUP_SYSTEM = (
    "For each NEW intent, decide whether it substantially duplicates one of the EXISTING "
    "intents — i.e. the same question pattern over the same data, so one SQL template "
    "would serve both. Different grouping dimension, different measure, or a different "
    "subject table is NOT a duplicate. Return duplicate_of = the existing id, else null.")

_JUDGE_DUP_SCHEMA = {
    "name": "dup_verdicts",
    "schema": {"type": "object", "required": ["verdicts"], "properties": {
        "verdicts": {"type": "array", "items": {"type": "object",
            "required": ["new_id", "duplicate_of"], "properties": {
                "new_id": {"type": "string"},
                "duplicate_of": {"type": ["string", "null"]}}}}}},
}


async def judge_duplicates(existing: list[dict], new: list[dict]) -> dict[str, str | None]:
    """判追加批里每条新意图是否与已有意图实质重复(同一问题模式问同一份数据)。"""
    payload = {
        "existing": [{"id": it["id"], "one_liner": it["one_liner"], "brief": it["brief"]}
                     for it in existing],
        "new": [{"id": it["id"], "one_liner": it["one_liner"], "brief": it["brief"]}
                for it in new],
    }
    messages = [
        {"role": "system", "content": JUDGE_DUP_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    result = await llm.complete(messages, tier="light", max_tokens=2048,
                                json_schema=_JUDGE_DUP_SCHEMA, tag="intent-judge-dup")
    return {v["new_id"]: v["duplicate_of"] for v in result["verdicts"]}
