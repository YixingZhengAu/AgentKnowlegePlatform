# server/app/core/

**职责**:与业务无关的机制层代码(日志、错误、中间件、Trace 框架、问答编排)。

| 文件 | 内容 |
| --- | --- |
| `logging.py` | structlog 配置、`request_id_ctx`、`get_logger()` |
| `errors.py` | `AppError` 家族 + `register_exception_handlers()`(统一错误体) |
| `middleware.py` | `RequestContextMiddleware`:分配 request_id、记访问日志 |
| `trace.py` | `traced()` 计时/记账 + `ChatContext` buffer + `flush_traces()` 批量落库 |
| `chat.py` | `chat_events()`(唯一编排)+ `run_chat()`(非流式入口,D4) |

详见 `architect.md`。
