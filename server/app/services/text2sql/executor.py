"""执行闸:一条 SQL 允不允许打到客户库上(B6 的 `gate_and_execute` 原样迁入)。

**这是应用器之后的最后一道关,不是唯一一道**。前面三道:
  ① 模板 SQL 是人工验收过的;② 应用器只用模板 AST 部件 + 校验过的字面量重建 SQL;
  ③ 数据库账号只有 SELECT 权限。
这一道拦的是"前面三道都被绕过"的假设:单条 SELECT、表列必须在语义层白名单里、
LIMIT 强制不超过上限、读超时。四项里任何一项不过 → 抛错,**不执行**。

★ 为什么白名单用的是"语义层"而不是"库里有什么":语义层是治理开关的落地
  (停用的表/列不出现在里面)。于是"这张表不许用于问数"这件事,在这里也是硬约束,
  不只是生成期的建议。
★ 行上限与超时来自 `.env`(TEXT2SQL_MAX_ROWS / TEXT2SQL_QUERY_TIMEOUT_SEC),
  默认值就是 B6 实测定稿的 500 / 15s。改它之前先跑 S3 评测集。
"""

from __future__ import annotations

import asyncio
import time
from functools import partial

import sqlglot
from sqlglot import exp

from app.config import settings
from app.services.text2sql import bizdb, sqltext
from app.services.text2sql.bizdb import BizConn

#: 模板万一无 LIMIT 时补上的值(模板静态校验要求必须有 LIMIT,正常不会触发)
FALLBACK_LIMIT = 200


def max_rows() -> int:
    return settings.text2sql_max_rows


def timeout_sec() -> int:
    return settings.text2sql_query_timeout_sec


def gate_and_execute(conn: BizConn, sql: str, layer: dict, *, preview: int = 5) -> dict:
    """执行前最后一道闸:单条 SELECT、白名单表列、强制 LIMIT、超时;返回结果与 sanity 标记。

    `preview` 只决定回带几行样本(默认 5,与运行时 trace 一致)。治理台的 Run 面板要多带
    几行才看得出数对不对,所以它是个参数 —— 闸的判定与 `sql_executed` 一个字都不受它影响。
    """
    stmts = sqlglot.parse(sql, dialect="mysql")
    if len(stmts) != 1 or not isinstance(stmts[0], exp.Select):
        raise ValueError("gate: exactly one SELECT statement is allowed")
    tree = stmts[0]

    tables = {t["name"]: {c["name"] for c in t["columns"]} for t in layer["tables"]}
    alias_to_table = {t.alias or t.name: t.name for t in tree.find_all(exp.Table)}
    for name in alias_to_table.values():
        if name not in tables:
            raise ValueError(f"gate: table {name} not in semantic layer whitelist")
    proj_aliases = {pr.alias for pr in tree.expressions if isinstance(pr, exp.Alias)}
    all_cols = set().union(*tables.values())
    for c in tree.find_all(exp.Column):
        if c.table:
            real = alias_to_table.get(c.table)
            if real is None or c.name not in tables[real]:
                raise ValueError(f"gate: column {c.table}.{c.name} not in whitelist")
        elif c.name not in proj_aliases and c.name not in all_cols:
            raise ValueError(f"gate: column {c.name} not in whitelist")

    limit = tree.args.get("limit")
    if limit is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(FALLBACK_LIMIT)))
    elif int(limit.expression.this) > max_rows():
        limit.set("expression", exp.Literal.number(max_rows()))
    # 多行排版:这条 SQL 会原样进引用卡给用户看(`runtime.py::citations` 的 snippet),
    # 排版只加空白,执行的和展示的仍是逐字同一份
    final = sqltext.render(tree)

    t0 = time.perf_counter()
    cols, rows = bizdb.query(conn, final, timeout=timeout_sec())
    # 取数耗时单独记:改写与执行原来是合计一个数,trace 面板里分不开谁慢(C5 要的)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    flags = ["empty_result"] if not rows else []
    return {"sql_executed": final, "cols": cols, "rowcount": len(rows),
            "elapsed_ms": elapsed_ms,
            "sample": [list(r) for r in rows[:preview]], "flags": flags}




async def agate_and_execute(conn: BizConn, sql: str, layer: dict, *, preview: int = 5) -> dict:
    """异步壳。闸的判定是纯 AST 计算,只有取数那一步需要离开事件循环。"""
    return await asyncio.to_thread(partial(gate_and_execute, conn, sql, layer, preview=preview))
