# server/tests/

**职责**:pytest 测试(pytest + pytest-asyncio,`asyncio_mode = "auto"`,不用挂 marker)。

| 文件 | 覆盖 |
| --- | --- |
| `test_providers.py` | Protocol 一致性、单例、价格换算、JSON 轻量校验、透传 rerank |
| `test_trace.py` | `traced()` 计时/异常记录、seq 递增、`summarize()` 截断、用量汇总 |
| `test_jobs.py` | Job 注册表、步骤声明、`step_<name>` 约定分发、假任务 payload 形状 |
| `test_staging.py` | payload 浅合并语义、审核状态推导、状态计数、S0 未注册 publisher |

跑:`cd server && uv run pytest`(全部离线,不打真实 API、不连 DB)。
真实调用的验证在 `scripts/smoke_*.py`。

详见 `architect.md`。
