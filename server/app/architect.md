# server/app/architect.md

## config.py

- `Settings`(pydantic-settings):`env_file` 指向**仓库根的 .env**(`REPO_ROOT/.env`),不是 server/.env
- `MissingConfigError`:把 pydantic 的字段名翻译成 .env 变量名,启动即报"缺哪一行"
- `_must_be_async_driver`:DATABASE_URL 不含 `+asyncpg` 直接拒绝启动
- `model_for_tier("main"|"light")`:业务代码不写型号名,只说要强还是快
- `settings.embedding_dim`:向量维度唯一出处(模型层、migration 都读它)
- 模块底部 `settings = get_settings()`,全局单例(`lru_cache`)

## db.py

- `engine`:`pool_pre_ping=True`(容器重启后不会拿到死连接)、pool_size=10
- `get_session()`:FastAPI 依赖,异常自动 rollback
- 演示业务库(demo_biz)**不共用这个引擎**,S3 用只读账号按需连

## main.py

- `create_app()` 的顺序见 server/architect.md
- lifespan 里 DB 探活失败只 `log.warning`,不抛 —— 否则 /healthz 也起不来
