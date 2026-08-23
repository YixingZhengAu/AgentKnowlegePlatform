"""演示业务库(客户库)的连接层:DSN 加解密 + 只读连接 + 同步查询。

★ 三条纪律,每条都有理由:

1. **连接串明文永不落库、永不出接口**。`datasources.dsn_enc` 是 Fernet 密文,密钥来自
   env `SECRET_KEY`。加解密只在这个文件里,别处拿到的永远是密文或已建好的连接。
2. **同步 pymysql + 线程池**,不引异步 MySQL 驱动。问数的查询形态是"一条 SELECT、
   强制 LIMIT ≤500、15s 读超时",异步驱动买不到吞吐,却会把执行链换成一条与 Phase B
   实测路径不同的实现 —— 迁移无损的前提是执行路径不变。
3. **参数一律传 None 而不是空元组**(见 `query()` 的注释):模板 SQL 里有
   `DATE_FORMAT(x,'%Y-%m')` 这类字面 `%`,pymysql 在 args 非 None 时会拿它做 % 格式化,
   直接把 SQL 解析坏。这是 Phase B 真踩过的坑。

本文件只管"连得上、查得动";**允不允许执行这条 SQL** 是 `executor.py` 的事(执行闸)。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import pymysql
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.core.errors import ProviderError

#: 支持的方言。演示库是 MySQL;datasources.db_type 也放开了 postgres,
#: 但 S3 只实现 MySQL 一条 —— 没实测过的方言不该假装支持。
DIALECT = "mysql"


@dataclass(frozen=True, slots=True)
class BizConn:
    """一个业务库连接的全部要素(明文,只在进程内存活)。"""

    host: str
    port: int
    user: str
    password: str
    database: str

    def masked(self) -> str:
        """给日志和接口用的可读形态 —— 永远不含口令。"""
        return f"mysql://{self.user}@{self.host}:{self.port}/{self.database}"


def parse_dsn(dsn: str) -> BizConn:
    """`mysql+pymysql://user:pass@host:3307/db` → BizConn。"""
    u = urlparse(dsn)
    if not u.scheme.startswith("mysql"):
        raise ProviderError(
            f"Unsupported datasource dialect: {u.scheme}", code="datasource_dialect_unsupported")
    if not (u.hostname and u.path.lstrip("/")):
        raise ProviderError("Datasource connection string is incomplete",
                            code="datasource_dsn_invalid")
    return BizConn(
        host=u.hostname,
        port=u.port or 3306,
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        database=u.path.lstrip("/"),
    )


def build_dsn(conn: BizConn) -> str:
    return (f"mysql+pymysql://{conn.user}:{conn.password}"
            f"@{conn.host}:{conn.port}/{conn.database}")


# ---------------------------------------------------------------- 加解密


def _fernet() -> Fernet:
    """SECRET_KEY 就是 Fernet key(bootstrap.sh 用 `openssl rand -base64 32 | tr '+/' '-_'`
    生成的正是它要的 urlsafe base64 32 字节)。key 不合法要在这里报清楚,
    否则错误会以"解密失败"的形态出现在很远的地方。"""
    try:
        return Fernet(settings.secret_key.encode())
    except (ValueError, TypeError) as exc:
        raise ProviderError(
            "SECRET_KEY is not a valid Fernet key (44-char urlsafe base64). "
            "Generate one with: openssl rand -base64 32 | tr '+/' '-_'",
            code="secret_key_invalid",
        ) from exc


def encrypt_dsn(dsn: str) -> str:
    return _fernet().encrypt(dsn.encode()).decode()


def decrypt_dsn(dsn_enc: str) -> str:
    try:
        return _fernet().decrypt(dsn_enc.encode()).decode()
    except InvalidToken as exc:
        # 换过 SECRET_KEY 的库就是这个症状 —— 说清楚,别让人去查网络
        raise ProviderError(
            "Cannot decrypt the datasource connection string. "
            "SECRET_KEY has changed since it was saved; re-enter the connection details.",
            code="datasource_dsn_undecryptable",
        ) from exc


# ---------------------------------------------------------------- 连接与查询


def demo_conn() -> BizConn:
    """出厂演示数据源(`.env` 的 BIZ_DATABASE_URL)。冒烟脚本与 seed 用它。"""
    if not settings.biz_database_url:
        raise ProviderError(
            "BIZ_DATABASE_URL is not configured (see .env.example)", code="bizdb_not_configured")
    return parse_dsn(settings.biz_database_url)


def connect(conn: BizConn, *, timeout: int | None = None) -> pymysql.connections.Connection:
    t = settings.text2sql_query_timeout_sec if timeout is None else timeout
    return pymysql.connect(
        host=conn.host, port=conn.port, user=conn.user, password=conn.password,
        database=conn.database, charset="utf8mb4",
        connect_timeout=min(t, 10), read_timeout=t, write_timeout=t,
    )


def query(conn: BizConn, sql: str, params: tuple | None = None, *,
          timeout: int | None = None) -> tuple[list[str], list[tuple]]:
    """同步执行一条只读 SQL,返回 (列名, 行)。

    **params 为空时必须是 None,不能是 ()**:pymysql 只要 args 非 None 就会对 SQL 做
    % 格式化,模板里的 `DATE_FORMAT(d,'%Y-%m')` 会被当成占位符解析坏。这是 Phase B 真踩过的坑。
    模板 SQL 自带字面值,本来也不需要绑定参数 —— 值的合法性由改写期的应用器保证,
    不靠 DB 的参数绑定;introspection 那些查 information_schema 的语句才用 params。
    """
    with connect(conn, timeout=timeout) as c:
        cur = c.cursor()
        cur.execute(sql, params or None)
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, list(cur.fetchall())


async def aquery(conn: BizConn, sql: str, params: tuple | None = None, *,
                 timeout: int | None = None) -> tuple[list[str], list[tuple]]:
    """异步壳:把同步查询挪到线程,不堵事件循环。"""
    return await asyncio.to_thread(query, conn, sql, params, timeout=timeout)


async def test_connection(conn: BizConn) -> dict:
    """数据源"Test connection"按钮的后端:连上、拿版本、数一下表。"""
    def _probe() -> dict:
        with connect(conn, timeout=10) as c:
            cur = c.cursor()
            cur.execute("SELECT VERSION()")
            version = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
                (conn.database,))
            return {"ok": True, "server_version": version, "table_count": cur.fetchone()[0],
                    "target": conn.masked()}

    try:
        return await asyncio.to_thread(_probe)
    except pymysql.MySQLError as exc:
        # 面向用户的报错:说清是连不上还是权限不够,别把 pymysql 的元组抛到界面上
        code, msg = (exc.args + (None, None))[:2]
        return {"ok": False, "error": f"MySQL error {code}: {msg}", "target": conn.masked()}
