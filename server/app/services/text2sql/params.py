"""参数区解析 + AI 预填(B5 原样迁入):模板 → 参数卡片 → 模板包。

链路:定稿模板 SQL → sqlglot 确定性拆三区
  where 条件 → filter 参数 / select 输出列 → output 参数 / group by → groupby 参数
→ AI 依语义层预填 business_name/hint(hint = 运行时改写器的取值说明书)
→ 校验(覆盖全、非空、英文、时间参数含格式、枚举参数含全部取值)→ 模板包草稿。

模板包是"保存即发布"的最终格式,也是 B6 受约束改写的唯一输入,格式在此冻结:
  {intent, sql, params: {filters[], outputs[], groupbys[]}}

解析是纯确定性代码(B4 静态校验保证 WHERE 只有 AND 连接的 `列 op 字面量`,
SELECT 全部显式别名),LLM 只写说明文字、不碰结构 —— 结构错误零容忍,文字可人审。
prompt 与校验规则均为公开常量,评审报告从这里渲染,防文档漂移。
"""

from __future__ import annotations

import datetime
import json

import sqlglot
from sqlglot import exp

from app.services.text2sql.llm import complete
from app.services.text2sql.semantic import BUSINESS_CONTEXT
from app.services.text2sql.template import DATA_SPAN_NOTE, TODAY, has_cjk

MAX_PREFILL_ROUNDS = 2   # 首次预填 + 最多 2 轮问题回灌重写

_OP_SYMBOL = {exp.EQ: "=", exp.NEQ: "!=", exp.GT: ">", exp.GTE: ">=",
              exp.LT: "<", exp.LTE: "<=", exp.Like: "LIKE"}
_OP_WORD = {"=": "eq", "!=": "ne", ">": "gt", ">=": "ge", "<": "lt", "<=": "le",
            "LIKE": "like", "IN": "in", "BETWEEN": "between"}

# ------------------------------------------------------------ 确定性解析(无 LLM)

PARSE_RULES = [
    "WHERE:按 AND 展开为叶子条件,每个叶子 = 一个 filter 参数;记录 来源表列/操作符/字面默认值;"
    "BETWEEN → value_shape=range(双值),IN → list(多值),其余 → scalar",
    "SELECT:每个投影(B4 保证全部显式别名)= 一个 output 参数;记录 表达式/别名/单一来源列(纯列或单列函数)",
    "GROUP BY:每项 = 一个 groupby 参数;表达式与某投影一致时回链其别名(linked_output),便于改写器按别名指称",
    "param_id 命名:f_/o_/g_ + 列名或别名;同列多条件(如日期区间的 >= 与 <=)追加操作符词缀去重",
    "value_type 来自语义层列类型:enum_values 存在 → enum;date/time → date;int → integer;"
    "decimal/float → number;其余 → string",
    "解析后自检:三区条数与 SQL 实际一致(与人工点数核对)、来源列必须存在于语义层、别名唯一",
]


def _col_meta(layer: dict, table: str, column: str) -> dict:
    for t in layer["tables"]:
        if t["name"] == table:
            for c in t["columns"]:
                if c["name"] == column:
                    return c
    raise KeyError(f"{table}.{column} not in semantic layer")


def _value_type(meta: dict) -> str:
    t = meta["type"].lower()
    if meta.get("enum_values"):
        return "enum"
    if "date" in t or "time" in t:
        return "date"
    if "int" in t:
        return "integer"
    if "decimal" in t or "float" in t or "double" in t:
        return "number"
    return "string"


def _alias_map(tree: exp.Select) -> dict[str, str]:
    m: dict[str, str] = {}
    for t in tree.find_all(exp.Table):
        m[t.alias or t.name] = t.name
    return m


def _lit(node: exp.Expression):
    """字面量节点 → Python 值(供默认值序列化)。"""
    if isinstance(node, exp.Neg):
        v = _lit(node.this)
        return -v if isinstance(v, (int, float)) else v
    if isinstance(node, exp.Null):
        return None
    if isinstance(node, exp.Boolean):
        return bool(node.this)
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        return float(node.this) if "." in node.this else int(node.this)
    raise ValueError(f"not a literal: {node.sql(dialect='mysql')}")


def _where_leaves(tree: exp.Select) -> list[exp.Expression]:
    where = tree.args.get("where")
    if where is None:
        return []
    node = where.this
    leaves = list(node.flatten()) if isinstance(node, exp.And) else [node]
    return [lf.this if isinstance(lf, exp.Paren) else lf for lf in leaves]


def _source(node: exp.Expression, aliases: dict[str, str]) -> str | None:
    """表达式的单一来源列 `table.column`;纯列或恰含一列的表达式,否则 None。"""
    cols = list(node.find_all(exp.Column))
    if len(cols) != 1:
        return None
    c = cols[0]
    table = aliases.get(c.table) if c.table else next(iter(aliases.values()), None)
    return f"{table}.{c.name}" if table else None


def parse_params(sql: str, layer: dict) -> dict:
    """定稿模板 SQL → 三区参数骨架(确定性,business_name/hint 留空给 AI 预填)。"""
    tree = sqlglot.parse_one(sql, dialect="mysql")
    assert isinstance(tree, exp.Select)
    aliases = _alias_map(tree)

    filters: list[dict] = []
    for node in _where_leaves(tree):
        col = node.this
        src = _source(col, aliases)
        if src is None:
            raise ValueError(f"filter column has no single source: {node.sql(dialect='mysql')}")
        if isinstance(node, exp.Between):
            op, shape = "BETWEEN", "range"
            value = [_lit(node.args["low"]), _lit(node.args["high"])]
        elif isinstance(node, exp.In):
            op, shape = "IN", "list"
            value = [_lit(e) for e in node.expressions]
        else:
            op, shape = _OP_SYMBOL[type(node)], "scalar"
            value = _lit(node.expression)
        meta = _col_meta(layer, *src.split("."))
        filters.append({"param_id": f"f_{src.split('.')[1]}", "kind": "filter",
                        "source": src, "operator": op, "value_type": _value_type(meta),
                        "value_shape": shape, "default_value": value,
                        "predicate_sql": node.sql(dialect="mysql"),
                        "business_name": "", "hint": ""})
    # 同列多条件(日期区间等)追加操作符词缀去重
    from collections import Counter
    dup = {pid for pid, n in Counter(f["param_id"] for f in filters).items() if n > 1}
    for f in filters:
        if f["param_id"] in dup:
            f["param_id"] += f"_{_OP_WORD[f['operator']]}"

    outputs: list[dict] = []
    for pr in tree.expressions:
        assert isinstance(pr, exp.Alias), f"projection without alias: {pr.sql(dialect='mysql')}"
        outputs.append({"param_id": f"o_{pr.alias}", "kind": "output",
                        "expr": pr.this.sql(dialect="mysql"), "alias": pr.alias,
                        "source": _source(pr.this, aliases),
                        "business_name": "", "hint": ""})

    groupbys: list[dict] = []
    group = tree.args.get("group")
    for g in (group.expressions if group else []):
        gsql = g.sql(dialect="mysql")
        linked = next((o["alias"] for o in outputs if o["expr"] == gsql), None)
        name = linked or (gsql.split(".")[-1] if isinstance(g, exp.Column) else f"expr{len(groupbys)+1}")
        groupbys.append({"param_id": f"g_{name}", "kind": "groupby",
                         "expr": gsql, "source": _source(g, aliases),
                         "linked_output": linked, "business_name": "", "hint": ""})

    ids = [p["param_id"] for zone in (filters, outputs, groupbys) for p in zone]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate param_id after disambiguation: {ids}")
    return {"filters": filters, "outputs": outputs, "groupbys": groupbys}


# ------------------------------------------------------------ AI 预填 prompt

PREFILL_SYSTEM = f"""You are a senior analytics engineer annotating the parameters of a VERIFIED SQL template.

At runtime, an AI rewriter receives a user question plus this template and may ONLY:
change WHERE literal values, disable a WHERE condition, drop output columns, or drop
GROUP BY columns. It can never add or alter anything else. Your annotations are the
rewriter's ONLY instructions for each parameter, so write them for that audience.

For every parameter produce:
- business_name: a short human label in plain business English (2-6 words), as it would
  appear on a form. No SQL jargon, no table prefixes.
- hint: instructions to the rewriter. Content by kind:
  * filter: which user phrasings map to this parameter; how to take the value (exact
    format); and the DEFAULT/DISABLE semantics — when the user does not mention it,
    keep the template default? and when may it be disabled entirely?
    - date parameters: state the value format YYYY-MM-DD, that relative phrases
      ("last month") must be resolved to absolute dates anchored at {TODAY}, and the
      valid data window 2024-09-01 to 2026-08-23.
    - enum parameters: enumerate EVERY allowed value verbatim with a short meaning;
      values outside the list must be rejected, not guessed.
    - LIKE parameters: partial, case-insensitive contains-match; replace the default
      with the name fragment the user mentions, keeping the surrounding % wildcards.
  * output: what the column shows in business terms, and when the rewriter should keep
    or drop it (dropped only if the user asks for a narrower answer).
  * groupby: what dimension it represents and what dropping it does to the numbers
    (coarser aggregation); it may be dropped only if the user asks for less detail.

Rules:
- English only. Never contradict the SQL or invent capabilities beyond value-change/
  disable/drop. Be specific to THIS template's business meaning (use the intent brief).
- Every param_id from the input must appear exactly once; no extras."""

PREFILL_SCHEMA = {
    "name": "param_prefill",
    "schema": {
        "type": "object",
        "properties": {
            "params": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "param_id": {"type": "string"},
                        "business_name": {"type": "string"},
                        "hint": {"type": "string"},
                    },
                    "required": ["param_id", "business_name", "hint"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["params"],
        "additionalProperties": False,
    },
}

PREFILL_RULES = [
    "param_id 集合必须与骨架完全一致(不缺不多不重复)",
    "business_name 与 hint 全部非空,英文(CJK 字符零容忍)",
    "date 型 filter 的 hint 必须含格式说明 `YYYY-MM-DD` 与数据窗口",
    "enum 型 filter 的 hint 必须逐一含语义层枚举的每个取值字面",
    "LIKE 型 filter 的 hint 必须说明部分匹配(含 partial/contains/fragment 任一表述)",
    "问题回灌重写 ≤ 2 轮,超限报错终止(不静默放行)",
]

REPAIR_USER_TMPL = """Your annotations failed validation:
{problems}

Return the corrected FULL JSON (all params, same schema). Fix only what is wrong."""


def _enum_meanings(meta: dict) -> list[dict] | None:
    return meta.get("enum_values") or None


def build_prefill_messages(template: dict, skeleton: dict, layer: dict) -> list[dict]:
    """预填输入:业务背景 + 意图 + SQL + 参数骨架(附语义层列说明与枚举)。"""
    def enrich(p: dict) -> dict:
        e = {k: p[k] for k in p if k not in ("business_name", "hint")}
        if p.get("source"):
            meta = _col_meta(layer, *p["source"].split("."))
            e["column_info"] = {"display_name": meta["display_name"],
                                "description": meta["description"], "type": meta["type"],
                                "enum_values": _enum_meanings(meta)}
        return e

    payload = {
        "business_context": BUSINESS_CONTEXT,
        "intent": {k: template[k] for k in ("intent_id", "type", "one_liner", "brief")},
        "sql": template["sql"],
        "params": {zone: [enrich(p) for p in items] for zone, items in skeleton.items()},
        "notes": DATA_SPAN_NOTE,
    }
    return [{"role": "system", "content": PREFILL_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}]


def prefill_problems(result: dict, skeleton: dict, layer: dict) -> list[str]:
    """AI 预填结果校验;返回问题列表(空 = 通过)。规则清单见 PREFILL_RULES。"""
    probs: list[str] = []
    want = [p["param_id"] for zone in skeleton.values() for p in zone]
    got = [p["param_id"] for p in result.get("params", [])]
    if sorted(want) != sorted(got):
        probs.append(f"param_id mismatch: missing={sorted(set(want) - set(got))}, "
                     f"extra={sorted(set(got) - set(want))}, duplicates allowed=no")
        return probs
    by_id = {p["param_id"]: p for p in result["params"]}
    for zone in skeleton.values():
        for sk in zone:
            r = by_id[sk["param_id"]]
            for field in ("business_name", "hint"):
                if not r[field].strip():
                    probs.append(f"{sk['param_id']}: {field} is empty")
                if has_cjk(r[field]):
                    probs.append(f"{sk['param_id']}: {field} contains CJK; English only")
            if sk["kind"] != "filter":
                continue
            hint = r["hint"]
            if sk["value_type"] == "date" and "YYYY-MM-DD" not in hint:
                probs.append(f"{sk['param_id']}: date filter hint must state the YYYY-MM-DD format")
            if sk["value_type"] == "enum":
                meta = _col_meta(layer, *sk["source"].split("."))
                missing = [e["value"] for e in meta["enum_values"] if e["value"] not in hint]
                if missing:
                    probs.append(f"{sk['param_id']}: enum filter hint must list every allowed "
                                 f"value; missing {missing}")
            if sk["operator"] == "LIKE" and not any(w in hint.lower() for w in
                                                    ("partial", "contains", "fragment")):
                probs.append(f"{sk['param_id']}: LIKE filter hint must state partial/contains matching")
    return probs


# ------------------------------------------------------------ 组装模板包

async def build_package(template: dict, layer: dict) -> dict:
    """单个定稿模板 → 模板包草稿(确定性解析 + AI 预填 + 校验回灌 ≤2 轮)。"""
    skeleton = parse_params(template["sql"], layer)
    messages = build_prefill_messages(template, skeleton, layer)
    rounds = 0
    while True:
        result = await complete(messages, tier="main", max_tokens=4000,
                                json_schema=PREFILL_SCHEMA, tag=f"prefill-{template['intent_id']}")
        probs = prefill_problems(result, skeleton, layer)
        if not probs:
            break
        rounds += 1
        if rounds > MAX_PREFILL_ROUNDS:
            raise RuntimeError(f"{template['intent_id']}: prefill still invalid after "
                               f"{MAX_PREFILL_ROUNDS} repair rounds: {probs}")
        messages = messages + [
            {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)},
            {"role": "user", "content": REPAIR_USER_TMPL.format(problems="\n".join(f"- {p}" for p in probs))},
        ]
    by_id = {p["param_id"]: p for p in result["params"]}
    for zone in skeleton.values():
        for p in zone:
            p["business_name"] = by_id[p["param_id"]]["business_name"]
            p["hint"] = by_id[p["param_id"]]["hint"]
    return {
        "intent": {k: template[k] for k in
                   ("intent_id", "type", "bucket", "one_liner", "brief", "tables")},
        "sql": template["sql"],
        "params": skeleton,
        "prefill_rounds": rounds,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "human_edited": False,
    }
