# server/app/core/architect.md

## 统一错误体

对外固定格式,前端只认这一种:

```json
{"error": {"code": "not_found", "message": "...", "detail": null}}
```

异常类 -> 状态码 / code:

| 异常 | 状态码 | code |
| --- | --- | --- |
| `NotFoundError` | 404 | not_found |
| `ConflictError` | 409 | conflict |
| `ConfigError` | 500 | config_error |
| `ProviderError` | 502 | provider_error |
| `RequestValidationError` | 422 | validation_error |
| `SQLAlchemyError` | 503 | db_error |
| `ConnectionError` | 503 | db_error |
| 其他 | 500 | internal_error(带 request_id) |

**为什么单列 `ConnectionError`**:连不上 Postgres 时 asyncpg 抛的是裸
`ConnectionRefusedError`(OSError 子类),SQLAlchemy 不包装它 —— 不单独接住就会报成
internal_error,掩盖"数据库没起"这个真实原因。

## 日志

- `request_id_ctx`(ContextVar)由中间件写入,`_add_request_id` 处理器给每条日志附加
- dev 用 `ConsoleRenderer`(彩色),prod 用 `JSONRenderer`
- `uvicorn.access` 被禁用,访问日志由 `RequestContextMiddleware` 输出;`/healthz` 不记(降噪)

## 待加(后续 Step)

- Step 5:`trace.py`(`traced()` async context manager + buffer 落库)、`chat.py`(`run_chat()`)
- Step 7:`jobs.py`(`submit_job()` + 执行器基类 + 僵尸任务清理)
