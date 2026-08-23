"""SQL 文本排版 —— 「SQL 长什么样」的唯一出处。

**为什么需要这个文件**:sqlglot 的 `tree.sql()` 默认吐一整行,而模板 SQL 是要给人
**编辑和验收**的治理资产 —— 一行三四百字符的东西读不了也改不了(D4 编辑器的注释
一直写着"模板 SQL 是格式化过的多行文本",这个前提原先根本没成立)。

**排版只加空白,不动语义**:走的是 sqlglot 的 AST → `pretty=True` 重新生成,
和执行闸最后那次 `tree.sql()` 是同一条路,所以能安全用在落库前。
两处已知的等价改写(实测 7 条模板 + 真库执行全过):

* `orders o` → `orders AS o`(别名补 AS)
* `!=` → `<>`(MySQL 里完全等价)

反引号包住的保留字(如 i16 的 `` `year_month` ``)会**原样保留** —— 实测过,
这是当年 B4 那轮自修留下的东西,丢了 SQL 就跑不起来。

**绝不抛异常**:排版失败(人正编到一半、语法还不完整)就原样返回。
排版是呈现,不是校验;校验有自己的出处(`template.py::static_problems` 与执行闸)。
"""

import sqlglot

#: 全域唯一方言。和 `bizdb.DIALECT` / 执行闸保持一致:S3 只实测过 MySQL
DIALECT = "mysql"


def render(tree: sqlglot.exp.Expression) -> str:
    """已经在手上的 AST → 多行 SQL。给已经 parse 过的调用方用,省一次重复解析。"""
    return tree.sql(dialect=DIALECT, pretty=True)


def format_sql(sql: str) -> str:
    """SQL 文本 → 多行 SQL。解析不了就原样返回(见模块头「绝不抛异常」)。"""
    if not sql or not sql.strip():
        return sql
    try:
        tree = sqlglot.parse_one(sql, dialect=DIALECT)
    except Exception:
        return sql
    if tree is None:
        return sql
    return render(tree)
