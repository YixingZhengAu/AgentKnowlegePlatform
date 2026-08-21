# architect.md(根目录 · 全局导航)

**用途**:改代码前的第一站。在这里定位到「要改的东西在哪个目录」,再进那个目录的 `claude.md` / `architect.md` 往下钻。
根目录的 `claude.md` 角色由 `CLAUDE.md` 承担(它会被每次自动加载,所以只放规则,不放结构)。

## 0. 一句话架构

三类知识按容错率分层治理(精准问答对 / 文档 RAG / 智能问数),每类走同一条摄取流水线
(上传原料 → 异步加工 Job → 人工审核 Staging → 发布),Agent 在回答时路由到对应知识并强制引用。

## 1. 目录地图(带指路)

| 目录 | 放什么 | 往下看 |
| --- | --- | --- |
| `documents/` | 需求与设计文档(无代码) | 见下方第 2 节 |
| `server/` | FastAPI 后端全部代码,uv 管理 | `server/claude.md` |
| `web/` | React + Vite 前端(三栏工作台) | `web/claude.md` |
| `docker/` | Postgres init 脚本(建业务库与只读账号) | `docker/claude.md` |
| 根目录 | `Makefile` / `docker-compose.yml` / `.env.example` / `README.md` | 见下方第 3 节 |

## 2. 文档的唯一出处(改之前先确认改的是哪份)

| 要改的东西 | 唯一出处 | 纪律 |
| --- | --- | --- |
| 需求、模块边界、锁定决策 D1–D5 | `documents/PRD.md` | 改需求先改这里 |
| 当前阶段的步骤与验收 | `documents/S0-PLAN.md` | 每个 Step 完成后回填自测证据 |
| 表结构、字段定义 | `documents/DB-DESIGN.md` | **文档先于 migration**;两者不一致以文档为准 |
| 颜色、字体、组件样式 | `documents/UI-STYLE.md` | hex 只允许出现在 token 定义处 |
| 环境约定、依赖管理、索引机制 | `CLAUDE.md` | 精干优先,详细内容放各目录 architect.md |

## 3. 常改的东西在哪(按"我要改 X"索引)

| 我要改… | 去哪 |
| --- | --- |
| 加一个环境变量 | `server/app/config.py` + `.env.example` + 本地 `.env`(三处同步) |
| 换 LLM 型号 / 换 tier 映射 | 只改 `.env` 的 `LLM_MODEL_MAIN/LIGHT`,业务代码不写型号名 |
| 换供应商 / 加供应商 | `server/app/providers/`(步骤见该目录 architect.md 末节) |
| 改模型价格 | `server/app/providers/pricing.py`(价格是事实不是环境,不进 .env) |
| 问答链路加一个 stage | `server/app/core/chat.py` 里加一个 `async with traced(...)` 块;SSE 协议不用改 |
| 改 SSE 事件协议 | `server/app/api/architect.md` 是协议出处,改完前后端一起改 |
| 加一张表 / 改字段 | `documents/DB-DESIGN.md` → `server/app/models/` → migration(流程见 DB-DESIGN §10) |
| 加一个接口 | `server/app/api/`(新文件要在 `api/__init__.py` include)+ `server/app/schemas/` |
| 改错误码 / 错误格式 | `server/app/core/errors.py`(前端只认 `{"error":{code,message,detail}}`) |
| 加一个 CLI 脚本 | `server/scripts/`,跑法 `cd server && uv run python -m scripts.<name>` |
| 改容器/数据库初始化 | `docker/postgres/init/01-init.sql`,**改完必须 `make db-reset`** 才生效 |
| 加一个开发命令 | 根目录 `Makefile`(命令带 `## 说明`,会被 `make help` 列出) |
| 改颜色 / 字体 / 圆角 | `documents/UI-STYLE.md` → `web/src/index.css` 的品牌层(**全仓唯一 hex 出处**) |
| 加一个前端页面 | `web/src/pages/` + `web/src/App.tsx` 路由 + `AppLayout` 的 `NAV`/`TITLES` |
| 改前端取数 / 错误 toast | `web/src/api/{client,hooks}.ts` |
| 改前端流式渲染 | `web/src/api/sse.ts`(协议出处仍是 `server/app/api/architect.md`) |
| 改静态预览的假数据 | `web/demo/fixtures.ts`,然后 `make demo` |

## 4. 数据流(S0 骨架,后续阶段往里插 stage)

```
用户提问
  └─ POST /api/agents/{id}/chat  (Step 5)
       └─ chat_events()          core/chat.py —— 唯一编排(事件流);
          run_chat() 只是把它消费到底,所以评测执行器与 HTTP 共用一条链路(D4)
            ├─ [stage] route            S4 加
            ├─ [stage] retrieve_*       S1/S2/S3 各加一个
            └─ [stage] generate         S0 已有形状:providers.get_llm().stream()
       每个 stage 由 traced() 包住 → 攒在 ChatContext → 助手消息落库后批量写 traces 表
       → 前端右侧轨迹面板 / GET /api/traces/{message_id}

知识入库(三类共用一条线)
  上传 ingest_sources → submit_job → ingest_jobs(steps/progress/step_logs)
    → staging_items(待审核) → 人工审核 → publish → 各域 publisher 写正式表 + 建索引
```

## 5. 两个数据库(别搞混)

| 库 | 用途 | 账号 | 谁连 |
| --- | --- | --- | --- |
| `agent_system` | 本系统全部业务表 | `postgres` | `server/app/db.py` 的 engine |
| `clenergy_biz` | 演示业务库,问数的查询目标 | `biz_reader`(只读) | S3 按需连,**不共用上面的 engine** |

## 6. 当前进度

S0 Step 1–6 已完成:仓库骨架 / 30 张表 / 后端骨架 / Provider 抽象层 / Trace 框架 + 问答链路 / 前端壳。

`make db && make migrate && make seed && make dev` 之后:

- 页面 http://localhost:5173 —— 三栏工作台,能看到 seed 的 3 个 KB 与 1 个 agent;
  `/styleguide` 是 UI 验收对照页
- curl 也能直接流式聊天并查 trace:

```bash
curl -N -X POST localhost:8000/api/agents/<agent_id>/chat \
  -H 'Content-Type: application/json' -d '{"question":"..."}'
curl localhost:8000/api/traces/<message_id>
```

契约链路已生效:改后端字段名 → `make types` → 前端 `tsc` 报错(实测见 `web/architect.md`)。

下一步 Step 7:最小对话页(消费 `web/src/api/sse.ts`)+ 通用 Job 框架。
逐步进度见 `documents/S0-PLAN.md` §1。
