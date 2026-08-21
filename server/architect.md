# server/architect.md

## 分层

```
scripts/  CLI 入口(seed、导出 openapi、冒烟)
   |
app/api/       HTTP 路由:只做参数校验 + 调用,不写业务逻辑
app/services/  业务逻辑(S1 起填充)
app/core/      机制层:日志、错误、中间件;后续 trace / jobs / chat
app/providers/ 外部模型供应商抽象(Step 4)
app/models/    SQLAlchemy 模型,唯一的表结构代码出处
app/schemas/   Pydantic 出入参
app/db.py      engine / SessionLocal / get_session 依赖
app/config.py  全部配置(唯一 .env 读取处)
```

## 启动链路

`uvicorn app.main:app` -> `app.main.create_app()`:
1. `setup_logging()`(app/core/logging.py)
2. `RequestContextMiddleware`(app/core/middleware.py:分配 request_id)
3. `CORSMiddleware`(白名单来自 `settings.cors_origin_list`)
4. `register_exception_handlers(app)`(app/core/errors.py)
5. `include_router(api_router)`(app/api/__init__.py)
6. `lifespan`:建 storage 目录 + 探一次 DB(DB 不通只告警,让 /healthz 能报 unhealthy)

## 命令

在仓库根用 Makefile:`make migrate` / `make seed` / `make api` / `make types`。
直接跑:`cd server && uv run uvicorn app.main:app --reload`。
