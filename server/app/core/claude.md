# server/app/core/

**职责**:与业务无关的机制层代码(日志、错误、中间件、Trace 框架、问答编排)。

| 文件 | 内容 |
| --- | --- |
| `logging.py` | structlog 配置、`request_id_ctx`、`get_logger()` |
| `errors.py` | `AppError` 家族 + `register_exception_handlers()`(统一错误体) |
| `middleware.py` | `RequestContextMiddleware`:分配 request_id、记访问日志 |
| `trace.py` | `traced()` 计时/记账 + `ChatContext` buffer + `flush_traces()` 批量落库 |
| `chat.py` | `chat_events()`(唯一编排:`retrieve_exact_qa` → `retrieve_text2sql` → 命中短路 / 否则 `generate`)+ `run_chat()`(D4) |
| `jobs.py` | 通用 Job 框架:`submit_job` / `execute_job` / `retry_job` / 僵尸收尸 |
| `jobs_demo.py` | `DemoSleepJob`:验证框架用的假任务(可调慢、可注入失败、产出待审条目) |
| `staging.py` | 审核与发布骨架:payload 合并/状态推导、批量审、`publish_job()` + publisher 注册表 |

详见 `architect.md`。
