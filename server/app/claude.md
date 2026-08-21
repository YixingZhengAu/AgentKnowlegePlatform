# server/app/

**职责**:后端应用代码本体。

| 路径 | 说明 |
| --- | --- |
| `main.py` | 应用工厂 `create_app()`、lifespan |
| `config.py` | 全部配置(唯一读 .env 处);`settings.model_for_tier()` 做 tier→型号映射 |
| `db.py` | async engine / SessionLocal / `get_session()` 依赖 |
| `models/` | SQLAlchemy 模型(表结构代码出处) |
| `schemas/` | Pydantic 出入参 |
| `api/` | HTTP 路由 |
| `core/` | 机制层:日志、错误、中间件、Trace 框架、问答编排(后续 jobs) |
| `providers/` | LLM / Embedding / Rerank 抽象与实现(tier 化调用、重试、计价) |
| `services/` | 业务逻辑,按知识域分包;`__init__.py` 是唯一 Job 注册点,见 `services/claude.md` |

详见 `architect.md`。
