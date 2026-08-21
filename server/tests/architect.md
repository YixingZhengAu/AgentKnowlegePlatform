# server/tests/architect.md

## 运行

`cd server && uv run pytest`(配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]`:
`asyncio_mode = "auto"`、`testpaths = ["tests"]`)。

## 分工:离线测试 vs 冒烟脚本

| | 离线测试(这里) | 冒烟脚本(`scripts/smoke_*.py`) |
| --- | --- | --- |
| 花钱/联网 | 不 | 是 |
| 验什么 | 接口形状、本地逻辑、边界 | key 有效、网络通、模型真能干活 |
| 谁跑 | 每次改完随手跑 | Step 验收时手动跑 |

所以这里刻意**不 mock OpenAI 客户端**去测 `complete()` 的分支 —— mock 出来的
"通过"证明不了任何事;真实行为由冒烟脚本盯着。

## 已覆盖

- `test_providers.py`:registry 返回的实现符合三个 Protocol(`runtime_checkable`)、
  单例(客户端有连接池,重复 new 浪费连接)、`estimate_cost` 已知/前缀匹配/未知型号、
  `_validate_json` 的三种结果、`_response_format` 两种入参写法、透传 rerank 的顺序与截断
- `test_trace.py`:`traced()` 记 ok/error 两种状态并原样抛异常、seq 跨 stage 递增、
  `summarize()` 长字符串截断 + 列表截到 20 项 + Decimal 转字符串、`ChatContext` 汇总

## 计划覆盖(按价值排序,不追求覆盖率)

1. `chat_events()` 链路:注入假 LLMProvider,断言事件序列与 trace 阶段数(需要 DB)
2. Job 框架:失败步骤重跑、僵尸任务清理(Step 7 后)
3. 精准 QA 三档阈值分支(S1)

约定:需要 HTTP 的测试用 `httpx.ASGITransport` 直接打 app,不起真服务;
需要 DB 的测试用独立 database(别污染 `agent_system`)。
