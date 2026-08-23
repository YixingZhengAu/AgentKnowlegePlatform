"""运行时受约束改写(B6 原样迁入,准确率的最后一关)。

链路:用户问题 + 已发布模板包
  → LLM 产出结构化改写计划(不是 SQL):{feasible, infeasible_reason, outputs_selected[], filters[], groupbys_selected[], notes[]}
  → 确定性应用器:校验(越界代码级裁剪/拒绝,不回灌 LLM 重试)→ 在 sqlglot AST 上重建 SQL
  → 执行闸(单条 SELECT / 白名单 / 强制 LIMIT / 超时)→ 结果 + sanity 标记。

安全模型:最终 SQL 只由"模板 AST 部件 + 校验过的字面量"重建,结构上长不出
模板外的表/列/条件/操作符;字符串字面量经 sqlglot 转义,注入串只会变成普通文本值。
prompt / schema / 应用规则均为公开常量,评审报告从这里渲染,防文档漂移。
"""

from __future__ import annotations

import datetime
import json
import re

import sqlglot
from sqlglot import exp

from app.services.text2sql import executor, sqltext
from app.services.text2sql.bizdb import BizConn
from app.services.text2sql.params import _col_meta, _where_leaves
from app.services.text2sql.template import TODAY

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ------------------------------------------------------------ 改写计划 prompt

REWRITE_SYSTEM = f"""You are a constrained SQL rewrite PLANNER. You receive a user question and ONE
verified SQL template package. You never write SQL. You output a rewrite PLAN that a
deterministic program applies to the template. Everything outside your powers is
rejected by code, so be honest rather than creative.

Your ONLY powers:
1. Filters — for each filter param: keep its default, change its VALUE (same column,
   same operator), or disable it. Follow each filter's `hint` verbatim: it defines the
   value format, the allowed values, and the DEFAULT/DISABLE semantics.
2. Outputs — keep or drop output columns. `outputs_selected` = param_ids to KEEP.
3. Group-bys — keep or drop GROUP BY dimensions. `groupbys_selected` = param_ids to
   KEEP. Dropping a dimension makes the aggregation coarser; when you drop a groupby
   that has a `linked_output`, drop that output column too.

You can NEVER: add tables/columns/conditions, change an operator, reverse an
exclusion filter into an inclusion, reorder results, or change the LIMIT.

Value rules:
- Dates: absolute YYYY-MM-DD only. Resolve relative phrases ("last month", "Q1 2026")
  anchored at TODAY = {TODAY}. Data window is 2024-09-01 to 2026-08-23.
- value shape must match the param: scalar → single value; IN list → array of values;
  BETWEEN range → [start, end] with start <= end.
- Enum params: use ONLY values the hint allows, spelled exactly. Never guess.
- Set value to null when keeping the default or when the filter is disabled.

Plan rules:
- List EVERY filter param_id exactly once (enabled + value), even the unchanged ones.
- Keep all outputs and groupbys unless the user explicitly narrows the answer.
- If the user's CORE ask needs something outside your powers (a column/table/split/
  condition this template does not have, or an enum value outside the allowed list),
  set feasible=false and put the reason in `infeasible_reason`. If it is only a MINOR
  aspect, keep the template default for that aspect, stay feasible=true, and add a note
  saying what was not honored.
- infeasible_reason: when feasible=false, ONE short sentence addressed to the user —
  it is shown to them verbatim as the refusal. Say what this template can do and what
  the question asked for instead. Empty string when feasible=true.
- notes: short English strings — resolved date ranges, anything not honored,
  assumptions made. Empty array if the plan fully answers the question.

Return ONLY the JSON plan."""

REWRITE_SCHEMA = {
    "name": "rewrite_plan",
    "schema": {
        "type": "object",
        "properties": {
            "feasible": {"type": "boolean"},
            # ★ 拒答文案的唯一出处:它会被逐字显示给用户(见 `pipeline.answer`)。
            #   曾经是从 `notes` 里取第一条 —— 那条通常是"日期解析成了几号"这种记账,
            #   于是"问了利润率"换来一句讲日期的回答。理由必须有自己的字段。
            "infeasible_reason": {"type": "string"},
            "outputs_selected": {"type": "array", "items": {"type": "string"}},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "param_id": {"type": "string"},
                        "enabled": {"type": "boolean"},
                        "value": {},
                    },
                    "required": ["param_id", "enabled", "value"],
                    "additionalProperties": False,
                },
            },
            "groupbys_selected": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["feasible", "infeasible_reason", "outputs_selected", "filters",
                     "groupbys_selected", "notes"],
        "additionalProperties": False,
    },
}


def build_rewrite_messages(question: str, package: dict) -> list[dict]:
    """改写计划输入:用户原话 + 完整模板包(hint 即取值说明书)。"""
    payload = {
        "question": question,
        "today": TODAY,
        "package": {"intent": package["intent"], "sql": package["sql"],
                    "params": package["params"]},
    }
    return [{"role": "system", "content": REWRITE_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}]


async def make_plan(question: str, package: dict) -> dict:
    """LLM 单次产计划;不做合规回灌(合规由应用器代码裁决,不给模型第二次机会去猜)。"""
    from app.services.text2sql.llm import complete_json
    data, _ = await complete_json(
        build_rewrite_messages(question, package), tier="main",
        max_tokens=2500, json_schema=REWRITE_SCHEMA,
        tag=f"rewrite-{package['intent']['intent_id']}")
    return data


# ------------------------------------------------------------ 确定性应用器

APPLY_RULES = [
    "outputs_selected / groupbys_selected 中未知 param_id → 代码裁剪并记录(不进 SQL);"
    "有效输出列裁到 0 → 整体拒绝",
    "计划启用了模板不存在的 filter param_id → 硬违规整体拒绝(等于试图新增 WHERE 条件)",
    "filter 值校验:形态必须匹配(scalar/list/range,range 恰 2 值且 low ≤ high);"
    "date 必须为合法 YYYY-MM-DD;integer/number 必须为数值;"
    "enum 值必须在允许集 = 语义层枚举 ∪ 模板默认值;任何不合法 → 硬违规整体拒绝,不回灌 LLM 重试",
    "LIKE 值不含 % 时代码自动补 %value%(保持部分匹配语义)",
    "分组联动:被丢弃的 groupby 若有 linked_output,对应输出列强制同丢;"
    "分组查询中任何非聚合输出列,若其表达式不在保留分组中,也强制同丢(防 ONLY_FULL_GROUP_BY)",
    "ORDER BY 中引用被丢弃输出别名/被丢弃分组表达式的项自动剪除;LIMIT 永远保留模板值",
    "SQL 只由模板 AST 部件 + 校验过的字面量重建(字符串经 sqlglot 转义),"
    "结构上不可能产生模板外的表/列/条件/操作符",
    "执行闸:单条 SELECT、表列均在语义层白名单、LIMIT ≤ TEXT2SQL_MAX_ROWS、"
    "read_timeout TEXT2SQL_QUERY_TIMEOUT_SEC;0 行结果打 empty_result sanity 标记",
]


def _is_aggregate(expr_sql: str) -> bool:
    return sqlglot.parse_one(expr_sql, dialect="mysql").find(exp.AggFunc) is not None


def _enum_allowed(f: dict, layer: dict) -> set[str]:
    """enum 参数允许集:语义层枚举 ∪ 模板默认值(定稿模板的默认值天然合法)。"""
    meta = _col_meta(layer, *f["source"].split("."))
    allowed = {e["value"] for e in (meta.get("enum_values") or [])}
    dv = f["default_value"]
    allowed |= {str(v) for v in (dv if isinstance(dv, list) else [dv])}
    return allowed


def _check_scalar(v, f: dict, layer: dict) -> str | None:
    """单值校验;返回问题描述(None = 通过)。"""
    if isinstance(v, (list, dict)) or v is None:
        return f"{f['param_id']}: expected a scalar value, got {type(v).__name__}"
    if isinstance(v, bool):
        return f"{f['param_id']}: boolean is not a valid value here"
    vt = f["value_type"]
    if vt == "date":
        if not isinstance(v, str) or not _DATE_RE.match(v):
            return f"{f['param_id']}: date value must be YYYY-MM-DD, got {v!r}"
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            return f"{f['param_id']}: {v!r} is not a real calendar date"
    elif vt == "integer":
        if not isinstance(v, int):
            return f"{f['param_id']}: integer value required, got {v!r}"
    elif vt == "number":
        if not isinstance(v, (int, float)):
            return f"{f['param_id']}: numeric value required, got {v!r}"
    elif vt == "enum":
        if str(v) not in _enum_allowed(f, layer):
            return (f"{f['param_id']}: {v!r} is outside the allowed values "
                    f"{sorted(_enum_allowed(f, layer))}")
    elif vt == "string":
        if not isinstance(v, str) or not v.strip():
            return f"{f['param_id']}: non-empty string required, got {v!r}"
    return None


def _validate_value(v, f: dict, layer: dict) -> str | None:
    shape = f["value_shape"]
    if shape == "range":
        if not isinstance(v, list) or len(v) != 2:
            return f"{f['param_id']}: BETWEEN needs [start, end], got {v!r}"
        for item in v:
            if (p := _check_scalar(item, f, layer)):
                return p
        if str(v[0]) > str(v[1]):
            return f"{f['param_id']}: range start {v[0]!r} is after end {v[1]!r}"
    elif shape == "list":
        if not isinstance(v, list) or not v:
            return f"{f['param_id']}: IN needs a non-empty array, got {v!r}"
        for item in v:
            if (p := _check_scalar(item, f, layer)):
                return p
    else:
        return _check_scalar(v, f, layer)
    return None


def _to_lit(v) -> exp.Expression:
    if isinstance(v, bool):
        return exp.Boolean(this=v)
    if isinstance(v, (int, float)):
        return exp.Literal.number(v)
    return exp.Literal.string(str(v))


def _set_leaf_value(leaf: exp.Expression, f: dict, v) -> None:
    """把校验过的新值写回谓词 AST(列与操作符原封不动)。"""
    if f["operator"] == "BETWEEN":
        leaf.set("low", _to_lit(v[0]))
        leaf.set("high", _to_lit(v[1]))
    elif f["operator"] == "IN":
        leaf.set("expressions", [_to_lit(x) for x in v])
    else:
        if f["operator"] == "LIKE" and isinstance(v, str) and "%" not in v:
            v = f"%{v}%"
        leaf.set("expression", _to_lit(v))


def apply_plan(package: dict, plan: dict, layer: dict) -> dict:
    """计划 → 校验 → sqlglot AST 重建最终 SQL。规则清单见 APPLY_RULES。

    返回 {ok, sql, violations, adjustments}:violations 非空即整体拒绝(sql=None);
    adjustments 是代码级裁剪/联动记录,可执行但必须披露。"""
    violations: list[str] = []
    adjustments: list[str] = []
    p = package["params"]
    out_by_id = {o["param_id"]: o for o in p["outputs"]}
    gb_by_id = {g["param_id"]: g for g in p["groupbys"]}
    f_by_id = {f["param_id"]: f for f in p["filters"]}

    # -- 输出列:未知裁剪,按模板顺序保留
    asked_out = list(dict.fromkeys(plan.get("outputs_selected", [])))
    for pid in asked_out:
        if pid not in out_by_id:
            adjustments.append(f"unknown output {pid} trimmed from plan")
    keep_out = [o["param_id"] for o in p["outputs"] if o["param_id"] in asked_out]

    # -- 分组:未知裁剪,按模板顺序保留
    asked_gb = list(dict.fromkeys(plan.get("groupbys_selected", [])))
    for pid in asked_gb:
        if pid not in gb_by_id:
            adjustments.append(f"unknown groupby {pid} trimmed from plan")
    keep_gb = [g["param_id"] for g in p["groupbys"] if g["param_id"] in asked_gb]

    # -- 分组联动:分组查询里,非聚合输出列的表达式必须仍在保留分组中
    if p["groupbys"]:
        kept_gb_exprs = {gb_by_id[pid]["expr"] for pid in keep_gb}
        for pid in list(keep_out):
            o = out_by_id[pid]
            if not _is_aggregate(o["expr"]) and o["expr"] not in kept_gb_exprs:
                keep_out.remove(pid)
                adjustments.append(f"output {pid} force-dropped: its expression left "
                                   f"the GROUP BY (ONLY_FULL_GROUP_BY)")
    if not keep_out:
        violations.append("no valid output column remains after validation")

    # -- filter:未知启用 = 新增条件企图 → 硬违规;值不合法 → 硬违规
    states: dict[str, tuple[bool, object]] = {}
    for entry in plan.get("filters", []):
        pid = entry["param_id"]
        if pid in states:
            adjustments.append(f"duplicate filter entry {pid}; first one kept")
            continue
        if pid not in f_by_id:
            if entry.get("enabled"):
                violations.append(f"plan enables unknown filter {pid} "
                                  f"(adding a WHERE condition is not allowed)")
            else:
                adjustments.append(f"unknown disabled filter {pid} trimmed from plan")
            continue
        v = entry.get("value")
        if entry["enabled"] and v is not None:
            if (prob := _validate_value(v, f_by_id[pid], layer)):
                violations.append(prob)
                continue
        states[pid] = (bool(entry["enabled"]), v)
    missing = [f["param_id"] for f in p["filters"] if f["param_id"] not in states]
    if missing:
        adjustments.append(f"filters not mentioned in plan kept at default: {missing}")

    if violations:
        return {"ok": False, "sql": None, "violations": violations, "adjustments": adjustments}

    # -- AST 重建(只用模板部件 + 校验过的字面量)
    tree = sqlglot.parse_one(package["sql"], dialect="mysql")
    assert isinstance(tree, exp.Select)

    keep_aliases = {out_by_id[pid]["alias"] for pid in keep_out}
    dropped_aliases = {o["alias"] for o in p["outputs"] if o["param_id"] not in keep_out}
    tree.set("expressions", [pr for pr in tree.expressions if pr.alias in keep_aliases])

    leaves = _where_leaves(tree)
    assert len(leaves) == len(p["filters"]), "template filters out of sync with SQL"
    kept_preds: list[exp.Expression] = []
    for f, leaf in zip(p["filters"], leaves, strict=True):
        enabled, v = states.get(f["param_id"], (True, None))
        if not enabled:
            adjustments.append(f"filter {f['param_id']} disabled")
            continue
        if v is not None:
            _set_leaf_value(leaf, f, v)
        kept_preds.append(leaf)
    if kept_preds:
        combined = kept_preds[0]
        for pred in kept_preds[1:]:
            combined = exp.And(this=combined, expression=pred)
        tree.set("where", exp.Where(this=combined))
    else:
        tree.set("where", None)

    group = tree.args.get("group")
    dropped_gb_exprs = {g["expr"] for g in p["groupbys"] if g["param_id"] not in keep_gb}
    if group:
        kept = [g for g in group.expressions if g.sql(dialect="mysql") not in dropped_gb_exprs]
        if kept:
            group.set("expressions", kept)
        else:
            tree.set("group", None)

    order = tree.args.get("order")
    if order:
        kept_items = []
        for item in order.expressions:
            inner = item.this
            if isinstance(inner, exp.Column) and not inner.table and inner.name in dropped_aliases:
                adjustments.append(f"ORDER BY {inner.name} pruned (column dropped)")
                continue
            if inner.sql(dialect="mysql") in dropped_gb_exprs:
                adjustments.append(f"ORDER BY {inner.sql(dialect='mysql')} pruned (groupby dropped)")
                continue
            kept_items.append(item)
        if kept_items:
            order.set("expressions", kept_items)
        else:
            tree.set("order", None)

    return {"ok": True, "sql": sqltext.render(tree),
            "violations": [], "adjustments": adjustments}



# ------------------------------------------------------------ 全链路

async def rewrite(question: str, package: dict, layer: dict, conn: BizConn) -> dict:
    """问题 + 模板包 → 计划 → 应用 → 执行;每步产物全记录(trace 与评审都读它)。"""
    plan = await make_plan(question, package)
    record: dict = {"template": package["intent"]["intent_id"], "question": question,
                    "plan": plan}
    if not plan.get("feasible", False):
        record["status"] = "refused_by_planner"
        record["final_sql"] = None
        return record
    applied = apply_plan(package, plan, layer)
    record["violations"] = applied["violations"]
    record["adjustments"] = applied["adjustments"]
    if not applied["ok"]:
        record["status"] = "rejected_by_applier"
        record["final_sql"] = None
        return record
    record["final_sql"] = applied["sql"]
    try:
        record["execution"] = await executor.agate_and_execute(conn, applied["sql"], layer)
        record["status"] = "executed"
    except Exception as e:  # 执行闸拒绝或 SQL 错误:如实记录,不吞
        record["status"] = "execution_failed"
        record["execution_error"] = str(e)
    return record
