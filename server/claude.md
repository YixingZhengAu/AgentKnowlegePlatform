# server/

**职责**:FastAPI 后端全部代码,依赖用 uv 管理(加包一律 `uv add`)。

| 路径 | 说明 |
| --- | --- |
| `pyproject.toml` / `uv.lock` | 依赖定义与锁定,禁止手改依赖段 |
| `alembic.ini` | Alembic 配置;连接串由 `migrations/env.py` 从 .env 注入,ini 里不写密钥 |
| `app/` | 应用代码,见 `app/claude.md` |
| `migrations/` | 数据库迁移,见 `migrations/claude.md` |
| `scripts/` | CLI 脚本(seed / openapi 导出 / 冒烟),见 `scripts/claude.md` |
| `tests/` | pytest 测试,见 `tests/claude.md` |

详见 `architect.md`。
