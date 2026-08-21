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

**并行开发纪律**(结构调整时入册,记录见 `documents/S0-PLAN.md` §5):

- **migration 串行生成**:域开发者只改 `app/models/` 自己域的文件 + `documents/DB-DESIGN.md`
  自己域的节,**不自己跑 `alembic revision`** —— 合并时由集成者统一生成,避免 multiple heads
- **共享表红线**:`ingest_jobs` / `staging_items` / `publish_records` / `knowledge_bases`
  的 DDL 任何域不得动,不加"只有自己需要"的列;差异进 payload jsonb 或本域自己的表
- 域代码只落在 `app/services/<域>/`,禁止 import 兄弟域;Job 注册行只加在
  `app/services/__init__.py`(全局唯一注册点)
