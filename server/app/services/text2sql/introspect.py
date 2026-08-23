"""B1:业务库 schema introspection → SchemaSnapshot(**Phase B 原样迁入**)。

SchemaSnapshot 是后续所有 prompt(description 生成 / 意图生成 / 模板生成)的唯一供料格式,
B1 评审通过后即冻结,这里一个字段都没动。结构:

{
  "database": str,
  "generated_at": iso str,
  "tables": [{
    "name": str, "comment": str, "row_count": int,
    "columns": [{
      "name": str, "type": str,          # COLUMN_TYPE 原文,如 varchar(20) / decimal(12,2)
      "nullable": bool, "key": str|None,  # PRI / UNI / MUL
      "comment": str,                     # 可能为空 —— description 生成的存在意义
      "samples": [str],                   # <=5 个非空去重采样(全部转成字符串)
      "distinct_count": int,
      "is_enum_like": bool, "enum_values": [str]|None,
    }]
  }],
  "relations": [{
    "from_table": str, "from_column": str, "to_table": str, "to_column": str,
    "source": "foreign_key" | "name_heuristic",   # 后者需人工确认(真实场景常无 FK)
  }]
}

**同步实现,由调用方(Job)用 `asyncio.to_thread` 包起来**:一次 introspection 是几十条
小查询,改成异步逐条 await 只会把一段实测过的确定性代码换成另一段,没有收益。
落库(snapshot → table_meta/column_meta/relations)在 `semantic.py`。
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any

from app.services.text2sql import bizdb
from app.services.text2sql.bizdb import BizConn

# 枚举识别:仅字符串类与 tinyint(布尔)参与;distinct ≤ 20 且必须小于行数(排除自由文本)
_ENUM_CANDIDATE_TYPES = {"varchar", "char", "enum", "text", "tinyint"}
_ENUM_MAX_DISTINCT = 20
_SAMPLE_LIMIT = 5
_SAMPLE_MAXLEN = 80


def _to_str(v: Any) -> str:
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return format(v, "f")
    s = str(v)
    return s if len(s) <= _SAMPLE_MAXLEN else s[:_SAMPLE_MAXLEN] + "…"


def _list_tables(conn: BizConn, database: str) -> list[dict]:
    _, rows = bizdb.query(
        conn,
        "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
        (database,),
    )
    return [{"name": r[0], "comment": r[1] or ""} for r in rows]


def _list_columns(conn: BizConn, database: str, table: str) -> list[dict]:
    _, rows = bizdb.query(
        conn,
        "SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
        "ORDER BY ORDINAL_POSITION",
        (database, table),
    )
    return [
        {
            "name": r[0], "type": r[1], "_data_type": r[2],
            "nullable": r[3] == "YES", "key": r[4] or None, "comment": r[5] or "",
        }
        for r in rows
    ]


def _foreign_keys(conn: BizConn, database: str) -> list[dict]:
    _, rows = bizdb.query(
        conn,
        "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY TABLE_NAME, COLUMN_NAME",
        (database,),
    )
    return [
        {"from_table": r[0], "from_column": r[1], "to_table": r[2], "to_column": r[3],
         "source": "foreign_key"}
        for r in rows
    ]


def _heuristic_relations(tables: list[dict], fks: list[dict]) -> list[dict]:
    """列名启发:`foo_id` → 存在表 foo/foos/fooes 且其主键为 id,则视为逻辑关联。
    真实客户库常缺 FK,这条兜底是 B1 的核心价值之一;结果标 name_heuristic 供人工确认。"""
    covered = {(f["from_table"], f["from_column"]) for f in fks}
    by_name = {t["name"]: t for t in tables}
    found: list[dict] = []
    for t in tables:
        for c in t["columns"]:
            if not c["name"].endswith("_id") or (t["name"], c["name"]) in covered:
                continue
            base = c["name"][:-3]
            for cand in (base, base + "s", base + "es"):
                target = by_name.get(cand)
                if target and any(tc["name"] == "id" and tc["key"] == "PRI"
                                  for tc in target["columns"]):
                    found.append({"from_table": t["name"], "from_column": c["name"],
                                  "to_table": cand, "to_column": "id",
                                  "source": "name_heuristic"})
                    break
    return found


def build_snapshot(conn: BizConn) -> dict:
    database = conn.database
    tables = _list_tables(conn, database)
    for t in tables:
        _, cnt = bizdb.query(conn, f"SELECT COUNT(*) FROM `{t['name']}`")
        t["row_count"] = int(cnt[0][0])
        t["columns"] = _list_columns(conn, database, t["name"])
        for c in t["columns"]:
            col, tbl = c["name"], t["name"]
            _, d = bizdb.query(conn, f"SELECT COUNT(DISTINCT `{col}`) FROM `{tbl}`")
            c["distinct_count"] = int(d[0][0])
            _, s = bizdb.query(
                conn,
                f"SELECT DISTINCT `{col}` FROM `{tbl}` WHERE `{col}` IS NOT NULL "
                f"ORDER BY `{col}` LIMIT {_SAMPLE_LIMIT}")
            c["samples"] = [_to_str(r[0]) for r in s]
            enum_like = (
                c["_data_type"] in _ENUM_CANDIDATE_TYPES
                and c["key"] not in ("PRI", "UNI")
                and 0 < c["distinct_count"] <= _ENUM_MAX_DISTINCT
                and c["distinct_count"] < t["row_count"]
            )
            c["is_enum_like"] = enum_like
            if enum_like:
                _, ev = bizdb.query(
                    conn,
                    f"SELECT DISTINCT `{col}` FROM `{tbl}` "
                    f"WHERE `{col}` IS NOT NULL ORDER BY `{col}`")
                c["enum_values"] = [_to_str(r[0]) for r in ev]
            else:
                c["enum_values"] = None
            del c["_data_type"]

    fks = _foreign_keys(conn, database)
    relations = fks + _heuristic_relations(tables, fks)
    return {
        "database": database,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "tables": tables,
        "relations": relations,
    }
