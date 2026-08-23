"""SQL 模板生成(B4 原样迁入,text2sql 的核心)。

链路:已采纳意图 → 圈定语义层子集 → 分型 prompt(query/stats 双策略)
→ 结构化输出 {sql, design} → sqlglot 静态校验 → 真库试执行 → 报错回灌自修 ≤2 轮。

design 是结构化设计说明(join 路径 / 聚合口径 / 每个 WHERE 条件的业务理由),
不进模板、只进评审报告 —— 对抗"静默错答"(SQL 能跑但口径错)的人审抓手。
prompt 常量与校验规则清单均为公开常量,前端"生成模板"的说明与评审报告都从这里读,防文档漂移。

★ `TODAY` 是**模块导入时算一次**的(与实验床一致)。它进 prompt 用来把"最近 12 个月"
  解析成绝对日期字面量。长跑进程跨天了会怎样:新生成的模板用新的今天,已定稿的模板不受影响
  (模板里是字面量),运行时改写另有自己的 TODAY。所以这里不需要每次调用重算。
"""

from __future__ import annotations

import asyncio
import datetime
import json

import sqlglot
from sqlglot import exp

from app.services.text2sql import bizdb
from app.services.text2sql.bizdb import BizConn
from app.services.text2sql.intents import _layer_subset
from app.services.text2sql.llm import complete
from app.services.text2sql.semantic import BUSINESS_CONTEXT

TODAY = datetime.date.today().isoformat()
DATA_SPAN_NOTE = ("The demo database contains data from 2024-09-01 to 2026-08-23. "
                  "Pick default filter values that are guaranteed to match rows; "
                  "for identity filters pick a concrete value from sample_values.")
MAX_REPAIR_ROUNDS = 2   # 首次生成 + 最多 2 轮回灌自修
MAX_LIMIT = 500

# ---------------------------------------------------------------- 生成 prompt

GEN_RULES_COMMON = f"""You are a senior analytics engineer writing a VERIFIED SQL TEMPLATE for MySQL 8.

A template is a runnable SELECT with sensible LITERAL default values. At runtime a
constrained rewriter may only: change WHERE literal values, drop output columns, or
drop GROUP BY columns. It can NEVER add tables, columns or conditions. So the template
must already contain every column and condition a user is likely to vary, with good defaults.

Authoritative inputs:
- The intent (one_liner + brief). The brief is the business-caliber contract: implement
  EVERY caliber it states (exclusions, currency, grouping grain, ranking rule).
- The schema subset: tables with column descriptions and enum meanings, plus relations.
  Use ONLY these tables. Join ONLY along the given relations.

Iron rules for the SQL:
1. Exactly one SELECT statement. No CTEs, no subqueries, no UNION, no comments.
2. Every WHERE condition is `column <operator> literal`, operator in: = != > >= < <=
   BETWEEN IN LIKE. Combine conditions with AND only.
3. Time defaults are ABSOLUTE date literals (today is {TODAY}): e.g. "last 12 months"
   becomes `order_date >= '{{today minus 12 months}}'`. Never CURDATE()/NOW() arithmetic.
4. Every projected column has a readable snake_case English alias (e.g. AS customer_name).
   No SELECT *. Qualify every column with its table alias.
5. Always include a LIMIT (see the type strategy for the value).
6. When the brief says users identify things by name / SKU / order number, filter on that
   human-facing column (LIKE or =), not on a surrogate id.
7. English only.
8. At most ONE WHERE condition per business concept. Never redundant alternates such as
   both `status != 'x'` and `status IN (...)` on the same column — pick the single form
   that best matches the brief.
9. Identity filters (customer name, order number, SKU...): default to a CONCRETE example
   value taken from sample_values, never a match-all placeholder like LIKE '%'. The
   template's default run must read like a real answer to the intent.
10. When ranking or grouping by an entity, GROUP BY its primary key together with the
    displayed name, so distinct entities sharing a name are not merged.

Also return a `design` object that makes your decisions reviewable:
- join_path: the FROM/JOIN chain as plain text, or null for a single table.
- measures: for stats, each aggregate expression and its business meaning; null for query.
- group_by_dims: the GROUP BY expressions; null for query.
- default_filters: EVERY WHERE condition, with a one-line business reason (why) and the
  default value as a string.
- caliber_notes: one note per caliber stated in the brief, saying how the SQL implements it.
"""

STRATEGY = {
    "query": """Type strategy — QUERY (detail rows, no aggregation):
- No GROUP BY and no aggregate functions anywhere.
- ORDER BY the most natural recency/importance column (usually date DESC), then LIMIT 50.

Worked example (neutral schema, style reference only):
intent: "Query: Recent payments for a specific store" / brief: users vary the store (by
name), a date range, and payment methods; sorted by most recent.
{
 "sql": "SELECT s.name AS store_name, p.paid_at AS paid_at, p.method AS payment_method, p.amount AS amount_aud FROM payments p JOIN stores s ON p.store_id = s.id WHERE s.name LIKE '%Acme%' AND p.paid_at >= '2026-05-25' AND p.method IN ('card', 'cash') ORDER BY p.paid_at DESC LIMIT 50",
 "design": {"join_path": "payments p JOIN stores s ON p.store_id = s.id",
            "measures": null, "group_by_dims": null,
            "default_filters": [
              {"column": "stores.name", "operator": "LIKE", "value": "%Acme%",
               "why": "Users identify the store by name, not by id."},
              {"column": "payments.paid_at", "operator": ">=", "value": "2026-05-25",
               "why": "Default to the last 90 days of activity."},
              {"column": "payments.method", "operator": "IN", "value": "('card', 'cash')",
               "why": "Both common methods included by default; users may narrow."}],
            "caliber_notes": ["Amounts are shown as stored (AUD), no conversion."]}
}""",
    "stats": """Type strategy — STATS (aggregation, GROUP BY required):
- GROUP BY exactly the dimensions the brief implies. Monthly grain uses
  DATE_FORMAT(date_col, '%Y-%m').
- Aggregate at the correct grain: beware fan-out joins double-counting a parent measure.
- Ranking intents: ORDER BY the main aggregate DESC, LIMIT to the brief's top-N.
- Time-trend intents: ORDER BY the period ascending, LIMIT 200 as a safety cap.

Worked example (neutral schema, style reference only):
intent: "Stats: Monthly paid amount trend by store" / brief: sums payment amounts per
calendar month and store, excluding voided payments; users vary the date range.
{
 "sql": "SELECT DATE_FORMAT(p.paid_at, '%Y-%m') AS month, s.name AS store_name, SUM(p.amount) AS total_paid_aud FROM payments p JOIN stores s ON p.store_id = s.id WHERE p.paid_at >= '2025-08-23' AND p.status != 'voided' GROUP BY DATE_FORMAT(p.paid_at, '%Y-%m'), s.name ORDER BY month ASC LIMIT 200",
 "design": {"join_path": "payments p JOIN stores s ON p.store_id = s.id",
            "measures": [{"expr": "SUM(p.amount)",
                          "meaning": "Total paid amount in AUD per month per store."}],
            "group_by_dims": ["DATE_FORMAT(p.paid_at, '%Y-%m')", "s.name"],
            "default_filters": [
              {"column": "payments.paid_at", "operator": ">=", "value": "2025-08-23",
               "why": "Default trend window: last 12 months."},
              {"column": "payments.status", "operator": "!=", "value": "voided",
               "why": "Brief excludes voided payments from the caliber."}],
            "caliber_notes": ["Voided payments excluded per brief.",
                              "Grain is calendar month by payment date."]}
}""",
}


def gen_system(intent_type: str) -> str:
    return GEN_RULES_COMMON + "\n" + STRATEGY[intent_type]


TEMPLATE_SCHEMA = {
    "name": "sql_template",
    "schema": {
        "type": "object",
        "required": ["sql", "design"],
        "properties": {
            "sql": {"type": "string"},
            "design": {
                "type": "object",
                "required": ["join_path", "measures", "group_by_dims",
                             "default_filters", "caliber_notes"],
                "properties": {
                    "join_path": {"type": ["string", "null"]},
                    "measures": {"type": ["array", "null"], "items": {
                        "type": "object", "required": ["expr", "meaning"],
                        "properties": {"expr": {"type": "string"},
                                       "meaning": {"type": "string"}}}},
                    "group_by_dims": {"type": ["array", "null"],
                                      "items": {"type": "string"}},
                    "default_filters": {"type": "array", "items": {
                        "type": "object",
                        "required": ["column", "operator", "value", "why"],
                        "properties": {"column": {"type": "string"},
                                       "operator": {"type": "string"},
                                       "value": {"type": "string"},
                                       "why": {"type": "string"}}}},
                    "caliber_notes": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

REPAIR_USER_TMPL = ("Your previous answer failed these checks:\n{problems}\n\n"
                    "Return the corrected FULL JSON object (sql + design), fixing every "
                    "issue and keeping design consistent with the corrected SQL.")


def _sample_values(layer: dict, table_names: list[str]) -> dict:
    """每列的真实采样,供模型给身份类过滤挑具体默认值(而不是 LIKE '%' 这种占位符)。

    实验床阶段这里回读 `out/schema_snapshot.json`;正式路径里同一批采样就存在
    `column_meta.sample_values`,由 `semantic.load_layer()` 带进语义层 —— 值一样,少一个数据源。
    """
    return {t["name"]: {c["name"]: c.get("samples", []) for c in t["columns"]}
            for t in layer["tables"] if t["name"] in table_names}


def build_gen_messages(layer: dict, intent: dict) -> list[dict]:
    """组装生成消息:system = 铁律 + 分型策略 + 样例;user = 意图 + 语义层子集 + 列采样。"""
    user = json.dumps({
        "business_context": BUSINESS_CONTEXT,
        "intent": {k: intent[k] for k in ("id", "type", "bucket", "one_liner", "brief")},
        "schema_subset": _layer_subset(layer, intent["tables"]),
        "sample_values": _sample_values(layer, intent["tables"]),
        "notes_for_defaults": DATA_SPAN_NOTE,
    }, ensure_ascii=False, indent=1)
    return [{"role": "system", "content": gen_system(intent["type"])},
            {"role": "user", "content": user}]


# ---------------------------------------------------------------- 静态校验

# 评审报告从这份清单渲染;改校验代码必须同步改这里(同文件相邻,防漂移)。
STATIC_RULES = [
    "单条语句且必须是 SELECT;禁 CTE / 子查询 / UNION",
    "禁相对时间函数(CURDATE/NOW/SYSDATE/CURRENT_DATE...)—— 时间默认值必须绝对字面量",
    "引用的表 ⊆ intent.tables;每个列经别名解析后必须存在于语义层对应表(防幻觉列)",
    "禁 SELECT *;每个输出列必须带 snake_case 别名(可读列名)",
    "WHERE 仅 AND 连接;每个条件必须是 列 op 字面量,op ∈ {=, !=, >, >=, <, <=, BETWEEN, IN, LIKE}(B5 拆参数的前提)",
    "query 型:禁 GROUP BY / 聚合函数 / HAVING,必有 ORDER BY 与 LIMIT",
    "stats 型:必有 GROUP BY 与 ORDER BY 与 LIMIT",
    f"LIMIT 必须存在且 1..{MAX_LIMIT}",
    "SQL 全英文(无 CJK 字符)",
]

_ALLOWED_PREDS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
                  exp.Between, exp.In, exp.Like)
_TIME_FUNCS = {"curdate", "now", "sysdate", "utc_date", "utc_timestamp", "curtime"}


def has_cjk(text: str) -> bool:
    return any("⺀" <= ch <= "鿿" for ch in text)


def _is_literal(node: exp.Expression) -> bool:
    if isinstance(node, exp.Neg):
        return _is_literal(node.this)
    return isinstance(node, (exp.Literal, exp.Null, exp.Boolean))


def _pred_ok(node: exp.Expression) -> bool:
    """一个 WHERE 叶子条件是否为 `列 op 字面量` 简单形态。"""
    if isinstance(node, exp.Between):
        return (isinstance(node.this, exp.Column)
                and _is_literal(node.args["low"]) and _is_literal(node.args["high"]))
    if isinstance(node, exp.In):
        return (isinstance(node.this, exp.Column)
                and bool(node.expressions) and all(_is_literal(e) for e in node.expressions))
    if isinstance(node, _ALLOWED_PREDS):
        return isinstance(node.this, exp.Column) and _is_literal(node.expression)
    return False


def _where_problems(select: exp.Select) -> list[str]:
    where = select.args.get("where")
    if where is None:
        return []
    probs: list[str] = []
    stack = [where.this]
    while stack:
        node = stack.pop()
        if isinstance(node, exp.And):
            stack += [node.this, node.expression]
        elif isinstance(node, exp.Paren):
            stack.append(node.this)
        elif not _pred_ok(node):
            probs.append(f"WHERE condition not in simple `column op literal` form: {node.sql(dialect='mysql')}")
    return probs


def static_problems(sql: str, intent: dict, layer: dict) -> list[str]:
    """确定性静态校验;返回问题列表(空 = 通过)。规则清单见 STATIC_RULES。"""
    probs: list[str] = []
    if has_cjk(sql):
        probs.append("SQL contains CJK characters; must be English only")
    try:
        stmts = sqlglot.parse(sql, dialect="mysql")
    except sqlglot.errors.ParseError as e:
        return [f"SQL does not parse (mysql dialect): {e}"]
    if len(stmts) != 1 or not isinstance(stmts[0], exp.Select):
        return probs + ["must be exactly one SELECT statement"]
    tree = stmts[0]

    for cls, label in ((exp.CTE, "CTE"), (exp.Subquery, "subquery"), (exp.Union, "UNION")):
        if tree.find(cls):
            probs.append(f"{label} is not allowed")
    for f in tree.find_all(exp.Func):
        name = (f.sql_name() or "").lower()
        if isinstance(f, (exp.CurrentDate, exp.CurrentTimestamp, exp.CurrentTime)) or name in _TIME_FUNCS:
            probs.append(f"relative time function not allowed ({f.sql(dialect='mysql')}); use an absolute date literal")

    catalog = {t["name"]: {c["name"] for c in t["columns"]} for t in layer["tables"]}
    allowed = set(intent["tables"])
    alias_map: dict[str, str] = {}
    for t in tree.find_all(exp.Table):
        if t.name not in allowed:
            probs.append(f"table `{t.name}` not in intent tables {sorted(allowed)}")
        alias_map[t.alias or t.name] = t.name
    proj_aliases = {pr.alias for pr in tree.expressions if isinstance(pr, exp.Alias)}
    for c in tree.find_all(exp.Column):
        if not c.table:
            if c.name in proj_aliases:  # ORDER BY / GROUP BY 引用投影别名,合法
                continue
            if len(alias_map) > 1:
                probs.append(f"unqualified column `{c.name}` (multiple tables in scope)")
                continue
            tbl = next(iter(alias_map.values()), None)
        else:
            tbl = alias_map.get(c.table)
            if tbl is None:
                probs.append(f"column `{c.sql(dialect='mysql')}` uses unknown table alias `{c.table}`")
                continue
        if tbl in catalog and c.name not in catalog[tbl]:
            probs.append(f"column `{tbl}.{c.name}` does not exist in the schema")

    for s in tree.find_all(exp.Star):
        if not isinstance(s.parent, exp.AggFunc):  # COUNT(*) 合法,其余位置的 * 一律禁
            probs.append("SELECT * is not allowed; project explicit aliased columns")
            break
    for proj in tree.expressions:
        if not isinstance(proj, exp.Alias):
            probs.append(f"projection `{proj.sql(dialect='mysql')}` has no alias; every output column needs a readable snake_case alias")

    probs += _where_problems(tree)

    has_group = tree.args.get("group") is not None
    has_order = tree.args.get("order") is not None
    limit = tree.args.get("limit")
    if intent["type"] == "query":
        if has_group:
            probs.append("query-type template must not contain GROUP BY")
        if tree.find(exp.AggFunc):
            probs.append("query-type template must not contain aggregate functions")
        if tree.args.get("having"):
            probs.append("query-type template must not contain HAVING")
        if not has_order:
            probs.append("query-type template must have ORDER BY")
    else:
        if not has_group:
            probs.append("stats-type template must contain GROUP BY")
        if not has_order:
            probs.append("stats-type template must have ORDER BY")
    if limit is None:
        probs.append("template must have a LIMIT")
    else:
        try:
            n = int(limit.expression.name)
        except (AttributeError, ValueError):
            n = -1
        if not (1 <= n <= MAX_LIMIT):
            probs.append(f"LIMIT must be an integer in 1..{MAX_LIMIT}")
    return probs


# ---------------------------------------------------------------- 试执行与生成

def trial_execute(conn: BizConn, sql: str) -> tuple[list[str], list[tuple], str | None]:
    """真库试执行(只读账号)。含 DATE_FORMAT 的 % 字面量,bizdb.query 内已保证 args=None。"""
    try:
        cols, rows = bizdb.query(conn, sql)
        return cols, rows, None
    except Exception as e:  # noqa: BLE001 —— 报错文本回灌给 LLM 自修
        return [], [], f"{type(e).__name__}: {e}"


def _jsonable(v):
    return v if isinstance(v, (int, float, str, type(None))) else str(v)


async def generate_template(conn: BizConn, layer: dict, intent: dict) -> dict:
    """生成一条模板:静态校验 + 试执行不过则报错回灌,最多 MAX_REPAIR_ROUNDS 轮自修。"""
    messages = build_gen_messages(layer, intent)
    trace: list[dict] = []
    for round_no in range(MAX_REPAIR_ROUNDS + 1):
        data = await complete(messages, tier="main", max_tokens=3000,
                              json_schema=TEMPLATE_SCHEMA, tag=f"template-{intent['id']}")
        sql = data["sql"].strip().rstrip(";")
        problems = static_problems(sql, intent, layer)
        cols: list[str] = []
        rows: list[tuple] = []
        if not problems:
            cols, rows, err = await asyncio.to_thread(trial_execute, conn, sql)
            if err:
                problems = [f"execution error on the live database: {err}"]
            elif not rows:
                problems = ["query returned 0 rows on the live demo database; "
                            f"widen the default filter values ({DATA_SPAN_NOTE})"]
        if not problems:
            return {
                "intent_id": intent["id"], "type": intent["type"], "bucket": intent["bucket"],
                "one_liner": intent["one_liner"], "brief": intent["brief"],
                "tables": intent["tables"], "sql": sql, "design": data["design"],
                "trial": {"row_count": len(rows), "columns": cols,
                          "rows_preview": [[_jsonable(v) for v in r] for r in rows[:10]]},
                "repair_rounds": round_no, "repair_trace": trace,
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "human_edited": False,
            }
        trace.append({"round": round_no, "sql": sql, "problems": problems})
        messages = messages + [
            {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
            {"role": "user", "content": REPAIR_USER_TMPL.format(problems="\n".join(f"- {p}" for p in problems))},
        ]
    raise RuntimeError(f"{intent['id']}: still failing after {MAX_REPAIR_ROUNDS} repair rounds: {trace[-1]['problems']}")
