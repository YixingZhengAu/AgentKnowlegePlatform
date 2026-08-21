# S0 地基阶段 · 详细计划

**关联文档**:PRD.md §9(开发策略与顺序,同目录)
**日期**:2026-08-21
**阶段目标(DoD,一句话)**:`docker-compose up` + `make dev` 后能打开页面,发一句话,收到 LLM 流式回复,且 DB 里能查到这次对话的完整 trace。

**S0 的边界纪律**(做之前先记住不做什么):

- ❌ 不做任何一类知识的加工逻辑(那是 S1–S3 的事)
- ❌ 不做路由(S4)、不做评测界面(S6,只建表)
- ❌ 不做用户体系(硬编码一个 `default_user`)
- ❌ 不上 Celery / Redis / MinIO(BackgroundTasks + 本地磁盘够用)
- ✅ 只做「三个模块都确定会原样复用的东西」

**每个 Step 的完成纪律(自测后才算完)**:

任何一个 Step 做完,**不允许直接进入下一步**,必须依次完成:

1. 跑通该 Step 自己的「验收」小节里列出的全部检查项(命令要真的执行,不能只看代码"应该没问题");
2. 回归确认:前面 Step 已通过的验收项没有被本步改坏(至少重跑受影响的那几项,如 `make dev` 起服务、冒烟脚本);
3. 汇报时附上自测证据(跑了什么命令、关键输出/截图),再标记该 Step 完成。

自测不通过就修,修不动就如实报告卡点,**不允许带着已知失败进入下一个 Step**。

---

## 0. 开工前清单:已全部拍板(2026-08-21)

| # | 事项 | 结论 |
| --- | --- | --- |
| U1 | LLM API Key | **OpenAI**,key 已在本地 `.env`(main=gpt-5,light=gpt-5-mini) |
| U2 | Embedding | **OpenAI text-embedding-3-small,dim=1536**;Provider 接口保留可替换性 |
| U3 | Docker | 已装 Docker 28.4(开工时启动 Docker Desktop 即可) |
| U4 | Python / Node | 实测 **Python 3.13.5 + Node 24 + uv 0.8.19**,按此开发 |
| U5 | Rerank | **S0/S2 先用 PassthroughReranker 透传**,S2 跑通 RAG 后按实测效果决定是否引入真实 Rerank |
| U6 | 演示业务库位置 | **同一 Postgres 实例、单独 database `clenergy_biz`**,问数用只读账号连接 |
| U7 | 界面语言 | **英文单语**(平台面向澳洲用户):前端文案、Agent 交互、演示知识内容全英文;无 i18n。开发文档/注释仍中文(D5) |

---

## 1. 步骤总览

**进度**(2026-08-21):Step 1–9 全部 ✅ —— **S0 完成**(tag `s0-done`)

```
Step 1  仓库与环境骨架        →  git init、目录结构、docker-compose、Makefile
Step 2  数据库与全量建表      →  Alembic + 全部数据表一次建齐(含 eval 四张 + 摄取四张)
Step 3  后端骨架              →  FastAPI 应用工厂、配置、日志、统一错误、健康检查
Step 4  Provider 抽象层       →  LLM / Embedding / Rerank 三接口 + 默认实现 + CLI 冒烟脚本
Step 5  Trace 框架 + run_chat →  @traced 装饰器、最小问答链路、SSE 流式接口
Step 6  前端壳                →  Vite + React 脚手架、三栏布局、API client、类型生成
Step 7  最小对话页 + Job 框架 →  能聊天;Job 提交/查进度的通用机制(用假任务验证)
Step 8  通用审核台组件        →  泛型 Staging 审核界面(用假数据渲染验证)
Step 9  收尾验收              →  跑一遍 DoD 清单、写 README、打 tag
```

依赖关系:Step 1→2→3 严格串行;Step 4 与 Step 2 可并行;Step 5 依赖 3+4;Step 6 依赖 3(要有 openapi.json);Step 7 依赖 5+6;Step 8 依赖 6+2;Step 9 收尾。

---

## 2. 分步详细计划

### Step 1 · 仓库与环境骨架 ✅ 已完成

**做什么**

1. `git init`,建立单仓(monorepo)目录结构:

```
agent-system/
├── docker-compose.yml        # postgres(pgvector) 一个服务
├── docker/postgres/init/     # 首次建卷时执行:建 clenergy_biz + 只读账号 biz_reader
├── Makefile                  # make dev / make db / make types / make seed
├── .env.example              # 所有需要的环境变量模板(不含真实 key)
├── README.md
├── server/                   # FastAPI 后端
│   ├── pyproject.toml        # uv 管理依赖
│   ├── app/
│   │   ├── main.py           # 应用工厂
│   │   ├── config.py         # pydantic-settings 读 .env
│   │   ├── db.py             # engine / session
│   │   ├── models/           # SQLAlchemy models(按域分文件)
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── api/              # 路由,按模块分文件
│   │   ├── providers/        # LLM / Embedding / Rerank 抽象与实现
│   │   ├── core/             # trace / jobs / chat 等核心机制
│   │   └── services/         # 业务逻辑(S1 起填充)
│   ├── migrations/           # Alembic
│   ├── scripts/              # CLI 工具(冒烟、灌数据)
│   └── tests/
├── web/                      # React 前端
│   ├── package.json
│   └── src/
│       ├── api/              # client + types.gen.ts(自动生成)
│       ├── components/       # 通用组件(审核台在这)
│       ├── layouts/          # 三栏布局
│       └── pages/            # chat / kb / agent / settings
└── documents/                # PRD、本计划、后续设计文档(已建)
```

2. `docker-compose.yml`:`pgvector/pgvector:pg16` 镜像,挂本地卷,暴露 5432;init 脚本建两个 database:`agent_system`(系统库)与 `clenergy_biz`(演示业务库,U6)+ 一个只读账号 `biz_reader`(问数专用)。
3. `Makefile` 五个命令:`make db`(起库)、`make dev`(前后端一起起)、`make types`(openapi → TS 类型)、`make migrate`(跑迁移)、`make db-reset`(删库重建+migrate+seed,改表零成本的底气)。
4. `.env.example` 列出全部环境变量:`DATABASE_URL / LLM_PROVIDER / LLM_API_KEY / LLM_MODEL_MAIN / LLM_MODEL_LIGHT / EMBEDDING_PROVIDER / EMBEDDING_API_KEY / EMBEDDING_MODEL / EMBEDDING_DIM / FILE_STORAGE_DIR`。

**产出**:空仓库跑 `make db` 能起库,`docker ps` 能看到 pgvector 容器。

**需要你做的**:U3、U4(确认环境);把 U1 的 key 填进 `.env`(复制 `.env.example` 改名)。

**验收**:`docker exec` 进容器 `SELECT * FROM pg_extension` 能看到 `vector` 扩展。

**实际落地(与计划的差异)**:

- Makefile 实际有 10 个命令:计划的五个 + `db-stop` / `psql` / `api` / `web` / `install`(拆开单起前后端在调试时更方便)
- 脚本目录落在 `server/scripts/`(要 import app,必须在 uv 工程内),CLAUDE.md 已同步
- `.env.example` 比计划多了 `APP_ENV / LOG_LEVEL / CORS_ORIGINS / SECRET_KEY / BIZ_DATABASE_URL / RERANK_PROVIDER`
- 每个代码目录已按 CLAUDE.md 的索引机制补 `claude.md` + `architect.md`

**自测证据**:`make db` 起库成功;`pg_extension` 见 `vector 0.8.6` + `pgcrypto`;`\l` 见
`agent_system` 与 `clenergy_biz` 两个库;`biz_reader` 能连业务库、建表被拒(权限不足)、
连系统库被拒(无 CONNECT 权限)。

---

### Step 2 · 数据库与全量建表 ✅ 已完成

**做什么**

Alembic 初始化 + **一次性把全部表建齐**(改表比建表贵,这是 D4 决策的落地)。**字段级定义以 `DB-DESIGN.md`(同目录)为唯一出处,migration 照它写**。按域分组:

| 域 | 表 | S0 是否被使用 |
| --- | --- | --- |
| 知识库 | `knowledge_bases` | 建好,S1 用 |
| 精准 QA | `exact_qa_items` / `exact_qa_vectors` | 建好,S1 用 |
| 文档 | `documents` / `chunks` | 建好,S2 用 |
| 问数 | `datasources / table_meta / column_meta / relations / metrics / terms / rules / sql_examples` | 建好,S3 用 |
| **摄取骨架** | `ingest_sources / ingest_jobs / staging_items / publish_records` | **Step 7/8 就用(假任务验证)** |
| Agent | `agents / agent_kb_bindings` | 建好,S0 建一条硬编码 agent |
| 会话 | `conversations / messages / message_citations` | **Step 5 就用** |
| 观测 | `traces / feedbacks` | **Step 5 就用** |
| 评测 | `eval_sets / eval_cases / eval_runs / eval_results` | 建好,S6 用(D4 留口子) |
| 其他 | `users`(单行占位) / `unanswered_pool` | 建好 |

关键细节:

- 向量列用 `vector(EMBEDDING_DIM)`,维度从环境变量读 —— **这就是为什么 U2 要先定**:换 embedding 供应商=换维度=重建向量列。migration 里把维度写成配置驱动。
- `chunks.tsv` 建 `tsvector` 生成列 + GIN 索引(S2 的全文检索用),中文分词 S0 先用 `simple` 配置占位,S2 再评估 zhparser/jieba 方案。
- `staging_items.payload` 为 jsonb;`traces` 按 `message_id + stage` 建索引。

**产出**:`make migrate` 一次跑通;`scripts/seed_minimal.py` 灌入:1 个用户、1 个"默认助手" agent、3 个空 KB(三种类型各一)。

**需要你做的**:无(U2 的结论会影响 `EMBEDDING_DIM`,在 Step 4 前给到即可)。

**验收**:`\dt` 看到全部表;seed 后能查到默认 agent。

**实际落地**:

- 表数是 **30 张**(DB-DESIGN 文末写的 28 是笔误,已修正),模型在 `server/app/models/`,一域一文件
- 初始 migration `184b03b23dab`:开头 `CREATE EXTENSION IF NOT EXISTS vector/pgcrypto`
  让迁移自成一体;向量列维度用 `EMBEDDING_DIM = settings.embedding_dim`,不硬编码
- 依赖比计划多一个 `greenlet`(SQLAlchemy async 的硬依赖,alembic 首跑就暴露了)
- seed 内容全英文(D5),KB 绑定 priority = 精准QA 10 / 文档 20 / 问数 30,幂等可重复跑

**自测证据**:`make migrate` 一次跑通;`information_schema` 计数 31(30 表 + alembic_version);
三个向量列均为 `vector(1536)`;`chunks.tsv` 是 `ALWAYS GENERATED`;HNSW 索引 3 个 + GIN 索引 1 个;
`make seed` 两次、第二次全部跳过;`alembic check` 输出 "No new upgrade operations detected."。

---

### Step 3 · 后端骨架 ✅ 已完成

**做什么**

1. FastAPI 应用工厂:CORS、生命周期(启动时建连接池)、`/healthz`(含 DB 连通检查)。
2. `config.py`:pydantic-settings,所有配置从 `.env` 读,启动时校验缺失项并给出明确报错(比如没配 key 时直接告诉你缺哪个变量,而不是运行到一半 500)。
3. 统一错误体:`{"error": {"code": "...", "message": "...", "detail": ...}}`,全局异常 handler。
4. 结构化日志(loguru 或 structlog),每个请求带 request_id。
5. 第一批只读路由(为 Step 6 前端提供真实数据源):`GET /api/kbs`、`GET /api/agents`、`GET /api/conversations`。

**产出**:`make dev` 起后端,`/docs` 能看到 Swagger,`/healthz` 返回 ok。

**需要你做的**:无。

**验收**:关掉数据库容器时 `/healthz` 报 unhealthy 而不是崩溃。

**实际落地(两个值得记的坑)**:

1. **路径参数必须声明成 `uuid.UUID`**。写成 `str` 时非法 uuid 会一路走到 DB,
   报成 `db_error 503`,掩盖了"这是参数错误"。改成 UUID 后正确返回 `validation_error 422`。
2. **裸 `ConnectionRefusedError` 要单独接住**。DB 停掉时 asyncpg 抛的是 OSError 子类,
   SQLAlchemy 不包装它,导致业务接口报 `internal_error 500`。已在 `errors.py` 加
   `ConnectionError` handler,统一成 `db_error 503`。
3. 配置缺失的报错做了翻译:`MissingConfigError` 把 pydantic 字段名转成 .env 变量名,
   直接列出"缺 SECRET_KEY / OPENAI_API_KEY / DATABASE_URL"。

**自测证据**:`/healthz` 200 ok;三个只读接口 200,agent 详情带出 3 条 KB 绑定;
404/422 错误体格式统一;`make db-stop` 后 `/healthz` 返回 503 unhealthy、业务接口 503 db_error、
**后端进程未崩**;`make db` 恢复后无需重启后端即自动恢复(pool_pre_ping);
`ruff check` 全绿;`scripts.dump_openapi` 导出 7 条 path。

---

### Step 4 · Provider 抽象层(S0 技术核心之一)✅ 已完成

**做什么**

1. 定义三个 Protocol 接口(全部 async):

```python
class LLMProvider(Protocol):
    async def complete(self, messages, *, model_tier: Literal["main","light"],
                       temperature=0.3, max_tokens=2048, json_schema=None) -> LLMResult: ...
    async def stream(self, messages, *, model_tier="main", ...) -> AsyncIterator[StreamEvent]: ...

class EmbeddingProvider(Protocol):
    dim: int
    async def embed(self, texts: list[str]) -> list[list[float]]: ...   # 内部处理批量上限

class RerankProvider(Protocol):
    async def rerank(self, query: str, docs: list[str], top_n: int) -> list[RerankHit]: ...
```

2. 设计要点:
   - `model_tier`("main"/"light")而不是写死模型名 —— 业务代码只表达"要强模型还是快模型",具体型号在配置里映射。这是 PRD"分层用模型控成本"的落地,也是可讲的设计点。
   - `LLMResult` 统一带 `usage(prompt_tokens/completion_tokens)` 和 `cost_estimate`,Trace 框架直接消费。
   - `json_schema` 参数:结构化输出统一走这里(S1 抽取 QA、S4 路由决策都靠它),内部实现校验失败自动重试 2 次。
   - 统一的重试(指数退避)与超时;供应商特定的报错翻译成统一异常类型。
   - Rerank 先给 `PassthroughReranker`(原序返回),接口占位。
3. 按 U1/U2 的答案写默认实现(一个供应商一个文件)。
4. **CLI 冒烟脚本**(六步法第②步在 S0 的体现):

```bash
python -m scripts.smoke_llm        # 一次补全 + 一次流式 + 一次 JSON 模式,打印 token 与耗时
python -m scripts.smoke_embedding  # embed 三句话,打印维度和两两余弦相似度
```

**产出**:接口 + 实现 + 冒烟脚本。

**需要你做的**:**U1、U2 必须在此步前给到**;然后你亲手跑一遍两个冒烟脚本,确认 key 有效、网络通(如果你的网络需要代理访问 LLM API,这一步会暴露出来,请告诉我代理配置方式)。

**验收**:两个冒烟脚本全绿;拔掉 key 时报的是"配置缺失"类明确错误。

**实际落地(与计划的差异)**:

- 文件:`base.py`(Protocol + 返回类型)/ `registry.py`(按配置选实现,单例)/
  `openai_llm.py` / `openai_embedding.py` / `passthrough_rerank.py` /
  `pricing.py`(价格表,计划里没单列)/ `retry.py`(重试 + 异常翻译)
- `EmbeddingProvider` 多一个 `embed_detailed()`:`embed()` 只返回向量,但 trace 要 token 和成本,
  所以细节版单独给一个方法,接口仍然干净
- **推理型模型的坑(计划没预料到)**:gpt-5 系的思考 token 与回答共用
  `max_completion_tokens`。第一次冒烟传 `max_tokens=64`,64 个 token 全被思考吃光,
  `content` 是空字符串 —— "调用成功但没有回答"。处理:对 gpt-5/o 系型号自动追加
  `LLM_REASONING_HEADROOM`(默认 2048)并带 `reasoning_effort=low`,使 `max_tokens`
  的语义恒定为"给回答的预算";另加 `_guard_empty()`,拿到空回复直接抛错并写明怎么修
- **参数能力回退**:推理模型不接受 `temperature`。被 400 拒一次就记住"这个型号不支持这个参数",
  去掉重发且本进程后续不再带 —— 换型号不用改业务代码
- 配置多了 5 项:`LLM_REASONING_EFFORT / LLM_REASONING_HEADROOM / LLM_TIMEOUT_SEC /
  EMBEDDING_TIMEOUT_SEC / PROVIDER_MAX_ATTEMPTS / EMBEDDING_BATCH_SIZE`
- 顺手加了 `make smoke`(两个冒烟一起跑)与 `make test`(离线测试),以及
  `server/tests/test_providers.py` 10 个离线用例

**自测证据**:

- `make smoke` 全绿:补全 `text='SMOKE OK'` / 流式 44 chunks、first_token 1204ms /
  JSON 模式 `attempts=1` 且 `targets=["text2sql"]` 判对;embedding dim=1536、
  同义句余弦 **0.9033** vs 无关句 **0.1424**(向量真的有语义,不只是"跑通")
- 无效 key:报 `provider_auth_error` + "请检查 .env 里的 OPENAI_API_KEY";
  空 key:`config.py` 在 import 期就报 `MissingConfigError: OPENAI_API_KEY`
- `make test` 16 passed;`ruff check` 全绿

---

### Step 5 · Trace 框架 + `run_chat()` 最小问答链路(S0 技术核心之二)✅ 已完成

**做什么**

1. **Trace 框架**:一个 async context manager / 装饰器:

```python
async with traced(ctx, stage="generate", input={...}) as t:
    result = await llm.complete(...)
    t.output = {...}; t.usage = result.usage
```

   - 自动记录:阶段名、输入摘要、输出摘要、耗时 ms、token、成本、异常(异常也要落库,失败的 trace 更有价值)。
   - 挂在 `ChatContext` 上,一次问答的所有 stage 共享一个 `message_id`。
   - 写库用 buffer,请求结束统一 flush,不阻塞主链路。

2. **`run_chat()` 统一入口**(评测执行器与 HTTP 共用,D4 落地):

```python
async def run_chat(agent_id, conversation_id, question, *, stream=False) -> ChatResult | AsyncIterator[ChatEvent]
```

   S0 版本的内部链路刻意简单:`加载 agent → 存用户消息 → [stage: generate] 用 agent 的 system_prompt 调 LLM → 存回复 → flush traces`。**没有检索、没有路由** —— 那些是 S1/S4 往这个骨架里插的阶段。但链路的"形状"(stage 序列化、事件流协议)现在就定下来。

3. **SSE 接口** `POST /api/agents/{id}/chat`:事件协议现在定好,S1–S4 只增加事件类型不改协议:

```
event: stage_start   data: {"stage": "generate"}
event: token         data: {"text": "..."}
event: stage_end     data: {"stage": "generate", "latency_ms": 812, "usage": {...}}
event: done          data: {"message_id": "...", "citations": []}
```

4. `GET /api/traces/{message_id}`:返回该次问答的全部 stage 记录(Step 7 前端执行轨迹的雏形要用)。

**产出**:curl 能流式聊天;聊完 `traces` 表里有记录。

**需要你做的**:无。

**验收**:`curl -N` 调 chat 接口能看到 SSE 事件流;同一 message 的 trace 查询接口返回 generate 阶段的耗时和 token。

**实际落地(与计划的差异)**:

- **"单入口"的实现方式变了(更彻底)**:计划里 `run_chat(stream=bool)` 返回两种类型;
  实际做成**唯一的 async generator `chat_events()`**(永远产出事件流),
  `run_chat()` 只是把它消费到底拼成 `ChatResult`。于是流式与非流式不是两份代码,
  S1–S4 插阶段不可能只改到一边 —— D4 落得更实
- 事件协议比计划多一个 **`meta`**(第一个 token 之前就把 `message_id` /
  `conversation_id` 交给前端,新开会话时必须有它)和一个 **`error`**
- `conversation_id` 可以不传 = 新开一轮(前端"新对话"不需要先调建会话接口)
- 接口是 SSE / 非流式二合一(`stream` 字段),非流式返回体带 `trace` 数组
- 中断处理(计划没写,但演示一定会被问):客户端断开时按 `status="interrupted"` 落库

**四个踩过的坑(都已修,值得记)**:

1. **`stage_end` 不能在 `finally` 里 yield**。客户端断开时 finally 里 yield 会变成
   `RuntimeError: async generator ignored GeneratorExit`。移到 try/except 之后。
2. **中断落库不能直接 await**。捕获 `GeneratorExit/CancelledError` 时当前任务正在被取消,
   再 await 会立刻又被取消(第一版就是这样:日志有 interrupted,DB 里什么都没写)。
   改成 `_persist()` 自己开 session + `_detach()` 丢到后台任务(并持引用防 GC)后才真正落库。
3. **`vars()` 用不了 slots dataclass**。`ChatResult(slots=True)` 没有 `__dict__`,
   `ChatResponse(**vars(result))` 报 500;改用 `dataclasses.asdict()`。
4. **流一旦开始,状态码就定死 200**。之后抛异常全局 handler 也改不了,客户端只看到连接断掉。
   所以 `_sse_stream()` 把"编排还没开始就失败"也翻译成协议内的 `error` + `done`,
   前端永远只需要认一个终止信号。

**自测证据**:

- `curl -N` 流式:`meta → stage_start → 22×token → stage_end → done` 全部到齐;
  `stage_end` 带 `latency_ms=4807 / model=gpt-5 / usage / cost_usd=0.002354`
- `GET /api/traces/{message_id}`:1 条 generate,input 里能看到完整 prompt(含 system_prompt),
  output 带 `finish_reason=stop`,耗时/token/成本/型号齐全
- 多轮:带 `conversation_id` 再问一次,`prompt_tokens` 从 99 涨到 213(历史确实带进去了)
- 失败路径(故意用无效 key 起后端):`error` 事件 → 兜底话术走 `token` 事件 →
  `stage_end status=error` 且 error 文本入库 → `done status=failed`;**进程不崩**
- 中断路径:读 6 行就断开 → 日志 `chat_interrupted` → DB 里该消息
  `status=interrupted`、内容是已生成的片段、trace 有一条(latency 有、usage 空)
- DB 表实测:`messages` 里 user/assistant 成对,assistant 带 usage 与 latency_ms;
  `traces` 五条,四条 ok(gpt-5,cost 0.000491–0.002354)一条中断
- 回归:Step 3 的 6 个只读接口全 200;`404/422` 错误体格式未变;
  `make db-stop` 后流式与非流式都返回 `db_error 503`、`/healthz` unhealthy、进程存活,
  `make db` 后无需重启即自动恢复;`alembic check` 无新增变更;`ruff check` 全绿;
  `make test` 16 passed(新增 `test_trace.py` 6 个用例);openapi 9 条 path

---

### Step 6 · 前端壳 ✅ 已完成

**做什么**

1. Vite + React + TS + Tailwind + shadcn/ui 脚手架;ESLint + Prettier。**视觉规范以 `UI-STYLE.md`(同目录)为唯一出处**:Clenergy 官网风(navy #00205B 主色 + 黄 #FFCB02 强调),token 先行,组件禁裸色值。
2. **三栏布局骨架**(对话工作台的形状现在定):左侧导航(对话 / 知识库 / Agent / 设置四个入口)、中间内容区、右侧可折叠面板(执行轨迹的位置)。
3. API 层:
   - `make types`:openapi.json → `types.gen.ts`(openapi-typescript),这条链路 S0 就跑通并写进 Makefile;
   - fetch 封装(统一错误 toast、loading 态);
   - **SSE client**:封装 Step 5 的事件协议,暴露 `onToken / onStageStart / onStageEnd / onDone` 回调 —— 这是前端最需要先趟平的技术点。
4. 知识库列表页、Agent 列表页:纯只读表格,消费 Step 3 的接口(证明前后端类型链路是通的)。

**产出**:`make dev` 一条命令起前后端,页面能看到 seed 的 3 个 KB 和 1 个 agent。

**需要你做的**:无。语言已定(U7:英文单语),UI 风格已定(Clenergy 官网风,详见 `UI-STYLE.md`)。

**验收**:改一个后端字段名 → `make types` → 前端编译报错(证明契约链路生效)。

**实际落地(与计划的差异)**:

- **Tailwind v4,没有 `tailwind.config.js`**:v4 用 CSS 里的 `@theme` 取代了 v3 的
  `theme.extend`,所以 UI-STYLE §5.1 说的"index.css 变量 + theme.extend"在这里合成同一个文件。
  token 分三层:品牌原色(**全仓唯一允许写 hex 的地方**)→ 语义变量(shadcn 命名)→ Tailwind 工具类
- **shadcn/ui 用抄样式而不是跑 CLI**:S0 只需要 button/card/badge/table/input/skeleton 六个
  原生元素级的件,没引 Radix。`components.json` 留着,真需要 Dialog/Popover 时
  `npx shadcn add` 直接可用
- **不引 react-query、不引 toast 库**:`useApi` 40 行 + toast store 40 行,零依赖、好讲。
  Step 7 的 Job 轮询在 `useApi` 里加 `refetchInterval` 即可
- 页面比计划多两个:**Agent 详情页**(证明嵌套类型 `bindings` 链路通)和
  **Settings 页**(消费 `/healthz`,演示时"库通不通、维度多少"一眼可见)
- 顶栏没做面包屑:S0 只有一层详情页,详情页用返回链接更直接;真需要多级时再加
- dev 用 **Vite 代理**(`/api`、`/healthz` → 8000):前端一律写相对路径,
  于是开发环境同源、无 CORS 预检,SSE 也不受影响
- 顺手加了 `make lint`(ruff + eslint + tsc)与 `make smoke-sse`(前端 SSE 客户端打真后端)

**四个踩过的坑(都已修)**:

1. **TypeScript 7 装不上**:`typescript-eslint` 的 peer 是 `<6.1.0`、`openapi-typescript` 是
   `^5.x`,npm 直接 ERESOLVE。把 TS 钉在 `~5.9`
2. **CSS 注释里不能写 `bg-*/text-*`**:那个 `*/` 会提前闭合注释,Tailwind 报
   `CssSyntaxError: Invalid declaration`,报错信息还指向下一条 `@import`(很难看出是注释的问题)
3. **effect 里不能同步 setState**:新版 `eslint-plugin-react-hooks` 把
   `useEffect(() => setLoading(true))` 判成 error。改成用 `已装载的 key !== 当前 key`
   推导 `loading`,顺手也少了一轮渲染
4. **Node 原生跑 `.ts` 有两条约束**:相对 import 必须带 `.ts` 后缀(不做扩展名补全)、
   不能有不可擦除语法(已开 `erasableSyntaxOnly` 兜住)。
   这两条是为了让冒烟脚本能 import **产线的** SSE 客户端,而不是复制一份解析逻辑去验假的

**自测证据**:

- **契约链路(验收项)**:把 `KnowledgeBaseOut.description` 改名 → `make types` →
  `tsc -b` 报 `TS2339: Property 'description' does not exist`,位置直指 `KbListPage.tsx:52`;
  还原后编译通过
- **`make dev`**:一条命令起 8000 + 5173;`/healthz` 200、经代理的 `/api/kbs` 200
- **页面实测**(headless Chrome dump DOM 逐项断言,不是"看着像对"):
  `/kbs` 3 个 KB(含三色识别点 `bg-kb-exact-qa`/`document`/`text2sql`)、
  `/agents` 见 Clenergy Assistant + `rule_llm`、`/settings` 见 `dim=1536`/`env=dev`、
  `/chat` 右侧轨迹面板占位到齐、`/styleguide` 色值从 CSS 变量读回(`#00205b` 等)
- **SSE 客户端**(`make smoke-sse`,跑的是产线代码 `src/api/sse.ts`):
  直连 8000 与**穿 Vite 代理**各跑一次都通过 —— 事件顺序
  `meta → stage_start → token → stage_end → done` 正确、34 chunks 逐个到达
  (first_token 3.9s < 总耗时,证明代理没把流缓冲住)、`done.status=completed` 且带 trace
- **样式纪律自查**:`src/**/*.tsx` 里 hex 与 `rgb()` 出现次数为 0(唯一例外是侧栏叠加
  用 Tailwind 自带的 `bg-white/8`,即 UI-STYLE §3 指定的 `rgba(255,255,255,0.08)`)
- **回归**:`make test` 16 passed;`make lint` 全绿(ruff + eslint 0 warning + tsc);
  `npm run build` 成功且字体是本地打包(无 CDN);Step 3 的只读接口仍全 200;
  `alembic check` 无新增变更;`git status server/` 干净(临时改名已还原)

---

### Step 7 · 最小对话页 + 通用 Job 框架 ✅ 已完成

**做什么**

1. **对话页**:输入框、消息流、流式渲染(消费 SSE client)、会话列表(建/切/删)。右侧面板显示本次回答的 trace(阶段、耗时、token)—— 执行轨迹面板 v0。
2. **通用 Job 框架**(后端,三个模块的摄取都靠它):
   - `submit_job(job_type, source_id, params) -> job_id`:写 `ingest_jobs` + BackgroundTasks 派发;
   - Job 执行器基类:子类实现 `steps` 列表,框架负责逐步执行、更新 `progress` 与 `step_logs`、捕获异常写 `error`、支持从失败步骤重跑;
   - `GET /api/jobs/{id}`:进度查询。
3. **用一个假任务验证框架**:`DemoSleepJob`,4 个步骤各睡 2 秒随机日志。别小看它 —— S1 的抽取任务写出来之前,前端进度条组件需要一个稳定的联调对象。
4. 前端通用组件 `<JobProgress jobId>`:轮询 + 进度条 + 分步日志展开 + 失败重试按钮。

**产出**:能在页面上聊天看轨迹;能提交假任务看进度条走完。

**需要你做的**:无。

**验收**:DoD 主体达成 —— 页面发一句话,流式回复,右侧看到 trace,DB 可查;假任务中途 kill 后端进程再重启,任务状态是 failed 而不是永远 running(僵尸任务处理)。

**实际落地(与计划的差异)**:

- **"新建会话"接口没做,而且是刻意的**:后端不传 `conversation_id` 就等于新开一轮,
  所以前端点 New chat 只是清空本地状态 —— 少一次往返,也不会留下"建了会话但没发消息"
  的空数据。删除做成软删(`DELETE /api/conversations/{id}` → `status=archived`):
  对话与 trace 是演示时要复盘的证据,不真删
- **轨迹面板有两个数据源**(计划只写了"显示本次回答的 trace"):正在流的用 SSE 的
  `stage_end` 事件;点历史消息则去查 `GET /api/traces/{id}`,于是能**展开看当时
  实际发出去的 prompt 和 finish_reason** —— 演示时最有说服力的一屏
- **`useApi` 的 `refetchInterval` 做成了"可以是函数"**:轮询该不该继续得看刚拿回来的
  数据(任务到终态就停),写成常量做不到 —— 常量要在调用 useApi 之前算出来,那时数据还没回来
- **假任务顺带产出 20 条 `staging_items`**(计划只说"4 步各睡 2 秒"):
  Step 8 的审核台因此不需要另写灌数据脚本,`fail_at` 参数还能让指定步骤**只失败一次**
  (重跑就过)—— 不然"重试"按钮永远重试失败,演示不出恢复路径
- 顺手加了 `Stop` 按钮:abort fetch → 后端按 `status=interrupted` 落库(Step 5 已实现的
  中断路径,这一步终于有界面能演示它了)
- 页面比计划多一个 **Ingestion 页**(`/jobs`):进度条组件总得有个地方住,
  S1–S3 的摄取入口也长在这里
- 静态预览(`make demo`)一起升级了:预览里的对话是**真的在流** ——
  `demo/main.tsx` 返回一个按真协议推帧的 ReadableStream,由产线 `src/api/sse.ts` 解析

**四个踩过的坑(都已修)**:

1. **渲染期间不能写 ref**:`eslint-plugin-react-hooks` 的 `react-hooks/refs` 直接报 error。
   "把回调塞进 ref 保持最新"这个常见写法必须放到 effect 里做
2. **`done` 事件里的成本是独立字段,但落库时塞进了 `usage`**。不合并的话"刚答完的消息"
   没有成本、"从库里读回来的历史消息"有 —— 同一个组件两种形状。`onDone` 里合并解决
3. **trace 行的 key 不能只用 `seq + stage`**:阶段名和 seq 在不同消息里会重复,
   切消息时 React 复用了组件,展开状态串到另一条消息上
4. **`/api/jobs/types` 必须声明在 `/api/jobs/{job_id}` 之前**,否则 `types` 被当成
   uuid 参数吃掉,报 422

**自测证据**(交互路径用 CDP 真点按钮验,不是"看着像对"):

- **对话页**:输入 → 点 Send → 流式期间 Send 变 Stop、气泡内 `thinking…`、轨迹面板显示
  `generate…` 脉冲 → 流结束后气泡有正文 + `3.56 s / 94 + 12 tok`、轨迹面板 `generate`
  一行 + `1 stage / 3.56 s` 汇总、会话列表出现新会话(标题=首问)
- **历史消息**:点会话 → 消息加载 → 点轨迹行展开 → `INPUT` 里能看到完整 prompt
  (含 system_prompt)、`OUTPUT` 里有 `finish_reason`
- **中断**:发一个长问题,4 秒后点 Stop → 气泡标 `interrupted`;
  DB 里该消息 `status=interrupted`、`latency_ms=3996`、`total_tokens=0`,trace 有一条
- **假任务**:提交 → `running 25/50/75%` 逐步推进 → `review 100%`、四步日志齐全、
  `stats={"staged":20}`;DB 里 `staging_items` 20 条、置信度 0.62–0.95(审核台能筛)
- **失败与重跑**:`fail_at=extract` → 50% 停在 extract、错误信息透到界面、
  出现"Retry from 'extract'"按钮 → 点它 → 只从 extract 起重跑(fetch/parse 不重做)→ review 100%
- **僵尸任务(验收项)**:另起一个 8001 端口的后端,提交一个每步 30 秒的任务,
  3 秒后 `kill -9`。DB 里当时仍是 `running`;重启后启动日志
  `jobs_reaped count=1`,任务变 `failed` + `error.code=job_abandoned`,且**可以重跑**。
  另外把心跳手动拨回 5 分钟前,查询接口把它判成 `job_stalled`(第二道防线)
- **回归**:`make test` 24 passed(新增 `test_jobs.py` 8 个用例);`make lint` 全绿
  (ruff + eslint 0 warning + tsc);`make smoke-sse` 通过;`npm run build` 成功;
  Step 3 的只读接口仍全 200;`alembic check` 无新增变更;`make demo` 产物 715KB、
  预览里聊天/任务两页都实测可交互

---

### Step 8 · 通用审核台组件(S0 前端核心)✅ 已完成

**做什么**

前端泛型组件 `<StagingReview>`,S1/S2/S3 的审核界面都是它的实例化:

```tsx
<StagingReview
  jobId={...}
  itemRenderer={QaItemCard}        // 每类知识自己实现:列表项怎么画
  editorRenderer={QaItemEditor}    // 每类知识自己实现:右侧编辑表单
  originPanel={DocOriginViewer}    // 可选:原文对照面板
/>
```

组件负责的通用能力:

- 左列表 + 右编辑区布局;列表按 `review_status` / `confidence` 筛选排序;
- 单条 通过/驳回/修改,修改走 `PATCH /api/staging/{id}`(patch payload 的 jsonb);
- 批量勾选 → 批量通过/驳回;
- 键盘流:`j/k` 上下条,`a` 通过,`x` 驳回(审核几十条时效率差 5 倍,也是演示亮点);
- 底部"发布"按钮 → `POST /api/jobs/{id}/publish`(S0 后端只做通用骨架:把 approved 条目标记 published + 写 `publish_records`;各类型的"写正式表 + 建索引"由 S1–S3 各自实现的 publisher 完成)。

**验证方式**:素材不用另写脚本 —— Step 7 的假任务(`/jobs` 页点一下)就会产出 20 条
`qa_pair` 的 `staging_items`(置信度铺开在 0.62–0.95,筛选/排序有东西可筛)。
拿一个最简 `itemRenderer` 渲染,走通"筛选 → 修改 → 批量通过 → 发布"全流程。

**产出**:审核台组件 + staging 通用 API。

**需要你做的**:走一遍这个假数据审核流程,**从"未来每天要审几百条"的运营视角提体验意见**(列表密度、快捷键、批量交互)。这是 S0 唯一需要你认真体验反馈的界面,因为它定型后 S1–S3 都长这样。

**验收**:20 条假数据全流程走通;审核状态刷新页面不丢。

**实际落地(与计划的差异)**:

- **渲染器多了一个"兜底"**:`registry.ts` 里没登记的 `item_type` 落到 JSON 渲染器
  (直接看/改 payload)。好处很实际:S2 的切片任务写出来、渲染器还没动手时,
  审核台**已经能用**,不必等前端补齐才能验证后端
- **审核状态的推导规则放在后端**(`core/staging.py::derive_review_status`):
  显式传状态就听它的、只改了内容 = `modified`、什么都没传就保持原状。
  做成纯函数后可离线测,前端完全不用重复这套逻辑 —— 它只管把改动发上来
- **`payload` 的 PATCH 是顶层键浅合并**:只改 answer 不必回传整份;
  但 list(相似问/关键词)是整份替换 —— 深合并的话"删掉一个相似问"没法表达
- **计数走单独的 `GET /api/staging/summary`**,不在前端数:前端只有当前筛选下的条目,数不准
- **发布是 job 级动作**,所以路由是 `POST /api/jobs/{id}/publish` 而不是挂在 staging 下;
  `publisher` 注册表(`register_publisher`)是 S1–S3 写正式表的插入点,
  S0 一个都没注册 —— 所以发布后 `published_ref` 是 null,这是分层不是漏项
- **审核动作有前置状态闸**(计划没写):只有 `review` 状态的 job 能审。
  发布之后再"通过"一条,那条永远发不出去(发布接口不再受理),必须在后端拦
- 页面比计划多一个 **`/jobs/:jobId/review`**;`<JobProgress>` 跑完后也多了一个进审核台的按钮
- 静态预览(`make demo`)里的审核台**真的能改**:`demo/main.tsx` 把 fixture 数组当内存库,
  PATCH / 批量 / 发布都写进它 —— 通过一条之后计数与发布按钮真的会动

**四个踩过的坑(都已修)**:

1. **Pydantic 的 `pattern` 必须锚定**。`pattern="|".join(REVIEW_STATUSES)` 不加 `^$`,
   `xapprovedy` 也算合法,错值一路走到 DB 的 CHECK 才被拦 —— 422 变成 500
2. **`modified` 必须一起发布**。第一版只发 `approved`,结果"人工改过再通过"的条目
   永远发不出去(状态是 modified,发布时被过滤掉)
3. **发布后到 job 状态回来之间有个窗口**。`publish` 成功但 `GET /api/jobs/{id}` 还没返回时,
   界面仍允许"通过" —— 前端加 `justPublished` 立刻置只读,后端加 `job_not_reviewable` 兜底
4. **`h-[calc(100vh-…)]` 要把页面标题行算进去**。第一版只减了顶栏与 padding,
   于是批量操作栏和动作条被挤到视口外(截图里一眼可见,DOM 断言看不出来)

**自测证据**(接口用 curl,交互用 CDP 真点按钮):

- **接口**:PATCH 只传 payload → `review_status=modified` 且其它键原样保留;
  显式传 `approved` 时听显式的;非法状态 / 非法 sort → `422`;不存在的 item → `404`;
  批量 → `{"updated":3}`;`GET /summary` 计数与 DB 一致
- **发布**:`{"published":2,"item_counts":{"pending":17,"approved":1,"modified":1,"rejected":1,"published":2}}`;
  job 变 `published` 且 `stats={"staged":20,"published":2}`;
  `publish_records` 一条;`staging_items` 里 2 条 `published=t`
- **三个 409 都实测到**:重复发布 `job_not_publishable`;一条没通过就发 `nothing_to_publish`;
  发布之后再审(单条与批量)`job_not_reviewable`
- **界面全流程**(一次跑完 21 项断言):20 条列表、默认置信度升序(0.62 在最前)、
  改答案出现 `unsaved` → Save 后变 `modified`、`j/k` 走条目、`a` 通过并自动跳下一条、
  `x` 驳回、勾三条出现批量栏 → 批量通过返回 `{"updated":3}`、
  筛选 pending 后剩 17 条、`Publish 3 approved` → toast `Published 3 items` →
  状态变 published → **Approve 按钮禁用(只读)**
- **验收项"刷新不丢"**:刷新页面后审核与发布状态仍在(状态在库里,不在前端)
- **静态预览**:硬刷新回到 20 条 pending → 按 `a` 计数真的变 → 发布成功 → 状态 published;
  顺手回归对话页仍是真流式(`15 year structural warranty` 逐字渲染出来)
- **回归**:`make test` 32 passed(新增 `test_staging.py` 8 个用例);`make lint` 全绿;
  `alembic check` 无新增变更(Step 8 没动表);`make types` 后 openapi 19 条 path;
  `npm run build` 成功;`make demo` 产物 732KB

---

### Step 9 · 收尾验收 ✅ 已完成

**做什么**

1. 全新环境模拟:删掉本地容器和 venv,从 `git clone` 开始按 README 走一遍,凡是卡住的地方补文档或补自动化。
2. DoD 核对清单逐项打勾(见下)。
3. `git tag s0-done`。

**S0 最终验收清单**

- [x] `cp .env.example .env` 填 key → `make db && make migrate && make seed && make dev` 四条命令起全系统
- [x] 对话页流式聊天,右侧面板显示 trace(阶段/耗时/token/成本)
- [x] `traces` / `messages` / `conversations` 表数据完整
- [x] 两个冒烟脚本全绿
- [x] 假任务:提交 → 进度条 → 完成;kill 重启后无僵尸任务
- [x] 审核台:假数据全流程(筛选/编辑/批量/发布)走通
- [x] 改后端 schema → `make types` → 前端编译报错
- [x] README 支持陌生人从零起系统

**全新环境是怎么模拟的(与计划的差异,以及为什么)**:

计划写的是"删掉本地容器和 venv"。实际做法是**等价但不破坏现有数据**的版本:
`git clone` 到临时目录 → `cp` 一份 .env 并把 `DATABASE_URL` 指向**新建的空库**
`agent_system_fresh` → 在克隆里 `uv sync` / `make migrate` / `make seed` / 起后端 /
`npm install` / `npm run build`。这样"迁移从零跑通 + seed + 系统能用"全部被真的验证了,
而用户现有的容器与数据一行没动。验完删掉克隆(里面有真实 key 的副本)与临时库。

**自测证据(Step 9 这一轮实际跑的)**:

- **全新签出**:`git clone` → `uv sync` → `make migrate`(`Running upgrade -> 184b03b23dab`)
  → `make seed`(3 KB + 1 agent + 5 条绑定)→ 新库里 **31 张表**(30 业务 + alembic_version)、
  三个向量列都是 `vector(1536)`
- **全新签出下起后端**(8002 端口,不碰用户的 8000):`/healthz` `ok`、`/api/kbs` 3 条;
  非流式问答返回 `'FRESH OK'` + 1 条 trace(**证明 key/网络在全新签出下也通**);
  `API_BASE=http://localhost:8002 npm run smoke:sse` 全绿(用新库的会话计数=2 反证它真的打的是 8002)
- **全新签出下的摄取全流程**:提交任务 → `review 100% stats={"staged":6}` →
  批量通过 3 条 → 发布 `published=3`,`item_counts` 与库一致
- **前端全新签出**:`npm install` + `npm run build` 成功(产物 321KB JS / 24KB CSS)
- **契约链路(验收项,重跑)**:把 `StagingItemOut.review_status` 改名 → `make types` →
  `tsc -b` 报 `TS2339: Property 'review_status' does not exist`,位置直指
  `StagingReview.tsx:290`;还原后编译通过
- **两个冒烟脚本(验收项)**:`make smoke` 全绿 —— complete `text='SMOKE OK'`、
  流式 35 chunks(first_token 2060ms)、JSON 模式 `attempts=1` 判对 `text2sql`;
  embedding dim=1536、同义 **0.9033** vs 无关 **0.1424**
- **回归**:`make test` 32 passed;`make lint` 全绿;`alembic check` 无新增变更;
  `make smoke-sse`(打 8000)全绿
- `git tag s0-done`

**README 走查发现并补上的**:审核台的用法(筛选/键盘流/发布)与"不起后端也能看界面"
(`make demo`)之前没写进 README,已补。除此之外按 README 一路走没有卡点。

---

## 3. 你的参与点汇总(按时间顺序)

| 时点 | 事项 | 形式 |
| --- | --- | --- |
| ~~开工前~~ | ~~U1–U7~~ **已全部拍板**(见第 0 节) | — |
| Step 1 开始时 | 启动 Docker Desktop | 点一下 |
| Step 4 完成时 | 亲手跑 `make smoke`,确认 key/网络/代理没问题(我已跑通一次,你再跑一次确认你的环境) | 跑命令,贴结果 |
| Step 8 完成时 | **体验审核台假数据流程,从运营视角提意见** | 15 分钟试用 + 反馈 —— **仍待你做**(代码已交付,你的意见会带进 S1 的渲染器) |
| Step 9 | 按 README 从零起一遍系统(最好的文档测试就是你) | 半小时 —— 我已用 `git clone` + 空库模拟走了一遍(见 Step 9 自测证据),你亲手再走一遍更有意义 |

## 4. S0 完成后的状态(交接给 S1 的东西)

S1(精准 QA)开工时,以下东西已经存在、直接用,不需要再造:

1. 全部数据表(含 `exact_qa_items` / `exact_qa_vectors` / staging 四张表)
2. `LLMProvider.complete(json_schema=...)` —— 抽取 QA 对直接用 JSON 模式
3. `EmbeddingProvider` —— 一问一向量直接调
4. Job 框架 —— S1 只写一个 `QaExtractJob(steps=[parse, extract, expand, dedupe])`
5. `<StagingReview>` —— S1 只写 `QaItemCard` + `QaItemEditor` 两个渲染器
6. `run_chat()` 骨架 —— S1 在 generate 前插入一个 `retrieve_exact_qa` stage
7. SSE 协议与前端执行轨迹面板 —— S1 的检索 stage 自动出现在轨迹里
8. CLI 脚手架模式 —— S1 第一件事就是写 `scripts/extract_qa.py` 调 prompt

也就是说:**S1 的全部工作 = 1 个 Job 子类 + 2 个前端渲染器 + 1 个检索 stage + 1 个 publisher + 调 prompt**。这就是 S0 值 15% 投入的原因。
