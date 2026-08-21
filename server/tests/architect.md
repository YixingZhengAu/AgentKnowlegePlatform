# server/tests/architect.md

## 运行

`cd server && uv run pytest`

## 计划覆盖(按价值排序,不追求覆盖率)

1. `run_chat()` 链路:mock LLMProvider,断言 trace 阶段数与顺序(Step 5 后)
2. Job 框架:失败步骤重跑、僵尸任务清理(Step 7 后)
3. Provider 的 json_schema 重试逻辑(Step 4 后)
4. 精准 QA 三档阈值分支(S1)

约定:测试用 `httpx.ASGITransport` 直接打 app,不起真服务;需要 DB 的测试用独立 database。
