# Clenergy 企业知识 Agent 系统

企业知识分层治理 + Agent 路由问答的演示系统。三类知识按容错率分层:**精准问答对**(零改写)、**文档知识**(RAG + 强制引用)、**智能问数**(语义层 + Text2SQL)。

- 需求与架构:[documents/PRD.md](documents/PRD.md)
- 当前阶段计划:[documents/S0-PLAN.md](documents/S0-PLAN.md)
- 表结构唯一出处:[documents/DB-DESIGN.md](documents/DB-DESIGN.md)
- 前端风格唯一出处:[documents/UI-STYLE.md](documents/UI-STYLE.md)

> 界面与问答交互为英文单语(平台面向澳洲用户);开发文档与代码注释为中文。

## 环境要求

| 依赖 | 版本 |
| --- | --- |
| Python | 3.13 |
| uv | 0.8+(Python 依赖只用 uv,禁止 pip install) |
| Node | 22+(实测 24) |
| Docker | 28+(跑 Postgres 16 + pgvector) |

## 从零起系统

```bash
cp .env.example .env      # 填 OPENAI_API_KEY;SECRET_KEY 按注释里的命令生成
make install              # uv sync + npm install
make db                   # 起 Postgres(pgvector),首次会建 clenergy_biz 与 biz_reader
make migrate              # 建表
make seed                 # 灌最小数据:1 用户 / 1 agent / 3 个空 KB
make smoke                # 冒烟:确认 key 有效、网络通(真实调 LLM 与 Embedding)
make dev                  # 前端 :5173  后端 :8000(/docs 看 Swagger)
```

起来之后打开 http://localhost:5173:

- **Chat** —— 发一句话就能看到流式回复,右侧执行轨迹面板列出每个阶段的耗时 / token / 成本;
  点历史消息可以展开看当时实际发出去的 prompt。流式期间 Send 会变成 Stop(真中断,
  这条消息会按 `interrupted` 落库)
- **Knowledge Bases / Agents** —— seed 的 3 个 KB 与默认 agent(含 system prompt 与 KB 绑定)
- **Ingestion** —— 提交一个假任务(`demo_sleep`)看进度条走完四步;
  `Inject a failure at` 可以让某一步失败,然后用"从失败步骤重跑"恢复
- `/styleguide` 是 UI 验收对照页(隐藏路由)

也可以直接用 curl 试问答:

```bash
AGENT=$(curl -s localhost:8000/api/agents | python3 -c 'import sys,json;print(json.load(sys.stdin)["items"][0]["id"])')
curl -N -X POST localhost:8000/api/agents/$AGENT/chat \
  -H 'Content-Type: application/json' -d '{"question":"What can you help me with?"}'
# 拿 done 事件里的 message_id 查执行轨迹(阶段/耗时/token/成本)
curl localhost:8000/api/traces/<message_id>
```

## 常用命令

```
make help       列出全部命令
make db         起数据库(等到健康)
make psql       进系统库 psql
make migrate    跑 Alembic 迁移
make seed       灌最小演示数据
make db-reset   删库重建 + 迁移 + seed(会丢数据;改表阶段的常规操作)
make api        只起后端
make web        只起前端
make dev        前后端一起起
make smoke      冒烟:真实调 LLM 与 Embedding(验证 key/网络/代理)
make smoke-sse  冒烟:前端 SSE 客户端打真后端(需先起后端)
make test       跑离线测试(不联网、不连 DB)
make lint       后端 ruff + 前端 eslint + TS 编译
make demo       打静态预览单文件(fixture 数据,不用起后端)
make types      openapi.json -> web/src/api/types.gen.ts(前端禁止手写 API 类型)
```

## 目录结构

```
docker/          Postgres 初始化脚本(建业务库与只读账号)
server/          FastAPI 后端(uv 管理),详见 server/claude.md
web/             React + Vite 前端,详见 web/claude.md
documents/       PRD / 阶段计划 / 数据库设计 / UI 规范
```

## 两个数据库

| 库 | 用途 | 连接账号 |
| --- | --- | --- |
| `agent_system` | 本系统全部业务表(知识、摄取、会话、trace、评测) | `postgres` |
| `clenergy_biz` | 演示业务库,智能问数的查询目标 | `biz_reader`(只读,无 CREATE、无法连系统库) |
