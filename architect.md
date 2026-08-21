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
| `web/` | React + Vite 前端(Step 6 起) | `web/claude.md` |
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
| 加一张表 / 改字段 | `documents/DB-DESIGN.md` → `server/app/models/` → migration(流程见 DB-DESIGN §10) |
| 加一个接口 | `server/app/api/`(新文件要在 `api/__init__.py` include)+ `server/app/schemas/` |
| 改错误码 / 错误格式 | `server/app/core/errors.py`(前端只认 `{"error":{code,message,detail}}`) |
| 加一个 CLI 脚本 | `server/scripts/`,跑法 `cd server && uv run python -m scripts.<name>` |
| 改容器/数据库初始化 | `docker/postgres/init/01-init.sql`,**改完必须 `make db-reset`** 才生效 |
| 加一个开发命令 | 根目录 `Makefile`(命令带 `## 说明`,会被 `make help` 列出) |

## 4. 数据流(S0 骨架,后续阶段往里插 stage)

```
用户提问
  └─ POST /api/agents/{id}/chat  (Step 5)
       └─ run_chat()             core/chat.py —— 评测执行器与 HTTP 共用同一入口(D4)
            ├─ [stage] route            S4 加
            ├─ [stage] retrieve_*       S1/S2/S3 各加一个
            └─ [stage] generate         S0 已有形状
       每个 stage 由 traced() 包住 → 落 traces 表 → 前端右侧轨迹面板 / GET /api/traces/{message_id}

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

S0 Step 1–3 已完成(仓库骨架 / 30 张表 / 后端骨架)。
下一步 Step 4:Provider 抽象层(`server/app/providers/`)。逐步进度见 `documents/S0-PLAN.md` §1。
