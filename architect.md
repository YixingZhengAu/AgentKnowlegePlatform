# architect.md(根目录 · 全局导航)

**用途**:改代码前的第一站。在这里定位到「要改的东西在哪个目录」,再进那个目录的 `claude.md` / `architect.md` 往下钻。
根目录的 `claude.md` 角色由 `CLAUDE.md` 承担(它会被每次自动加载,所以只放规则,不放结构)。

## 0. 一句话架构

三类知识按容错率分层治理(精准问答对 / 文档 RAG / 智能问数),每类走同一条摄取流水线
(上传原料 → 异步加工 Job → 人工审核 Staging → 发布),Agent 在回答时路由到对应知识并强制引用。
路由的层级(说明页口径):**精准问答 / 智能问数 / 编排三者同级**(都注册意图,命中即执行),
**文档 RAG 是兜底**,再往下是「说没有依据」。**编排(workflow)是第四种知识** ——
只把前三种按签过字的顺序连起来,不产生新事实;当前**只有设计与占位页,没有后端**。

## 1. 目录地图(带指路)

| 目录 | 放什么 | 往下看 |
| --- | --- | --- |
| `documents/` | 需求与设计文档(无代码) | 见下方第 2 节 |
| `server/` | FastAPI 后端全部代码,uv 管理 | `server/claude.md` |
| `web/` | React + Vite 前端(三栏工作台) | `web/claude.md` |
| `data/` | 测试用示例 PDF(文档 RAG 的原料),纯素材无代码 | 直接看目录里的 PDF |
| `docker/` | Postgres init(扩展)+ 演示业务 MySQL(建表灌数)+ MinerU 解析镜像 | `docker/claude.md` |
| `deploy/` | 临时公网部署资产(装机 / 发布 / Caddy / systemd),给面试官看的那套 | `deploy/claude.md` |
| 根目录 | `bootstrap.sh` / `Makefile` / `docker-compose.yml` / `.env.example` / `README.md` | 见下方第 3 节 |

## 2. 文档的唯一出处(改之前先确认改的是哪份)

| 要改的东西 | 唯一出处 | 纪律 |
| --- | --- | --- |
| 需求、模块边界、锁定决策 D1–D5 | `documents/PRD.md` | 改需求先改这里 |
| 当前阶段的步骤与验收 | `documents/S0-PLAN.md`(S0)、`S1-PLAN.md`(S1)、`S3-PLAN.md`(S3)、`S2-PLAN.md`(S2,最新) | 每个 Step 完成后回填自测证据 |
| S3 实验床的原始评审证据(历史,非现行规格) | `documents/s3-lab-reviews/`(B1–B8 九份报告) | 只读存档;现行结论看 `S3-PLAN.md` |
| 表结构、字段定义 | `documents/DB-DESIGN.md` | **文档先于 migration**;两者不一致以文档为准 |
| 颜色、字体、组件样式 | `documents/UI-STYLE.md` | hex 只允许出现在 token 定义处 |
| 某个知识域的代码往哪写、并行开发纪律 | `documents/DOMAIN-DEV-GUIDE.md` | 域开发者开工前必读;冲突地图在它的 §5 |
| 环境约定、依赖管理、索引机制 | `CLAUDE.md` | 精干优先,详细内容放各目录 architect.md |
| 临时公网部署(AWS / HTTPS / 密码门 / 运维) | `documents/DEPLOY.md` | 部署资产在 `deploy/`;应用级初始化仍归 `bootstrap.sh` |

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
| 加一类异步任务(摄取) | 本域文件夹写 `JobRunner` 子类 + `@register_job`,注册行加在 `server/app/services/__init__.py`(唯一注册点) |
| 查现有异步任务有哪些 | `demo_sleep` / `qa_parse` / `qa_extract` / `t2s_sync_schema` / `t2s_describe` / `t2s_intents` |
| 改错误码 / 错误格式 | `server/app/core/errors.py`(前端只认 `{"error":{code,message,detail}}`) |
| 加一个 CLI 脚本 | `server/scripts/`,跑法 `cd server && uv run python -m scripts.<name>` |
| 改精准问答的解析/抽取/相似问/检索/采纳 | `server/app/services/exact_qa/`(该目录 claude.md 有文件索引) |
| 改精准问答的接口 / 图片出口 | `server/app/api/exact_qa.py` / `server/app/api/files.py` |
| 改智能问数的任何一环(语义层/模板/改写/执行闸/检索) | `server/app/services/text2sql/`(该目录 `architect.md` §2 有"我要改 X"细表) |
| 改问数的接口 | `server/app/api/text2sql.py` + `server/app/schemas/text2sql.py`;**清单在 `server/app/api/architect.md`**,改完 `make types` |
| 改 chat 里问数那一段的分岔 | `server/app/core/chat.py` 的 `retrieve_text2sql` 段;装配在 `services/text2sql/runtime.py`,拒答话术在 `pipeline.py` 顶部 |
| 改问数的命中阈值或空路由 | `services/text2sql/retrieve.py`;**改前先读该目录 architect.md §4** |
| 灌/重建问数的演示知识与向量 | `make seed-s3`(资产在 `server/scripts/fixtures/s3/`) |
| 改问数的数据源接入页(接库/测连/同步) | `web/src/domains/text2sql/DatasourcesPage.tsx`(D1) |
| 改问数的 Schema 治理页(描述/枚举/启用/AI 回填) | `web/src/domains/text2sql/SchemaPage.tsx`(D2);该目录 `architect.md` 有"我要改 X"细表 |
| 改问数的意图台账 / 批量生成 / 空路由负例面 | `web/src/domains/text2sql/IntentsPage.tsx`(D3) |
| 改问数候选的审核卡片或采纳语义 | `web/src/domains/text2sql/{renderers.tsx,actions.ts}`(D3;采纳只建 draft) |
| 改问数一条模板的验收台(SQL / Run / 参数区 / 问法 / 发布) | `web/src/domains/text2sql/{IntentDetailPage.tsx,SqlEditor.tsx}`(D4) |
| 改 chat 里问数命中怎么显示(结果表格 / 最终 SQL / 踩线提示) | `web/src/domains/text2sql/SqlCitation.tsx`(D5) |
| 改命中阈值或那两道关 | `.env` 的 `EXACT_QA_*` 三项;**改前先读 `documents/S1-PLAN.md` §5 M4** |
| 改文档 RAG 的切分 / 描述 / 检索 | `.env` 的 `DOC_RAG_*`;实现在 `server/app/services/document/`,该目录 `architect.md` 有"我要改 X"细表 |
| 改文档 RAG 的重排策略或阈值 | `.env` 的 `DOC_RAG_RERANK_*`;实现在 `server/app/providers/cross_encoder_rerank.py` |
| 改容器/系统库初始化 | `docker/postgres/init/01-init.sql`,**改完必须 `make db-reset`** 才生效 |
| 改演示业务库的表或数据 | `docker/mysql/init/02-schema.sql` / `gen_seed.py`(改生成器后 `make bizdb-seed-gen`),**改完必须 `make bizdb-reset`** |
| 改问数的执行闸(超时/行上限) | `.env` 的 `TEXT2SQL_*` 两项;闸的实现在 `server/app/services/text2sql/executor.py` |
| 改 How It Works 说明页的任何一句文案(主张/立场/架构六小节/**编排那一节**/署名/子页流程) | `web/src/pages/how-it-works/content.ts`(文案唯一出处,组件不写死句子) |
| 改 How It Works 的图(箭头零件 `FlowArrow` / 全局图 `SystemMapFigure` / **两级路由 `RoutingFigure`** / **编排 `WorkflowExampleFigure`**)/ 折叠区 / 字阶 | `web/src/pages/how-it-works/{figures.tsx,Section.tsx}`;字阶规范在 UI-STYLE §2「演示页字阶」 |
| 改路由层级的说法(谁跟谁同级 / 谁是兜底) | `web/src/pages/how-it-works/content.ts` 的 `ROUTING`(+ `REQUEST_PATH` 的出口、`COMPARISON` 的列序);后端固定顺序在 `server/app/core/chat.py`,它是同级之间的 tie-break |
| 改编排(第四种知识)的摄取占位页 | `web/src/domains/workflow/CanvasPage.tsx`(静态预览,零后端;道理只在说明页讲) |
| 改 How It Works 在侧栏里的子项 | `web/src/pages/how-it-works/content.ts` 的 `HOW_IT_WORKS_NAV`(AppLayout 只遍历,不硬编码) |
| 加一个开发命令 | 根目录 `Makefile`(命令带 `## 说明`,会被 `make help` 列出) |
| 新机器从零装环境 / 改装机步骤 | 根目录 `bootstrap.sh`(工具链检查 → .env → 依赖 → 库 → 迁移 → seed → 自检);**新增外部依赖或初始化步骤必须同步进它** |
| 部署到公网 / 改部署方式 | `deploy/`(本地 `aws_up.sh` 开机器 / `remote_deploy.sh` 五阶段 / `aws_down.sh` 拆;服务器侧 `provision.sh` + `release.sh`);步骤与运维手册在 `documents/DEPLOY.md` |
| 改颜色 / 字体 / 圆角 | `documents/UI-STYLE.md` → `web/src/index.css` 的品牌层(**全仓唯一 hex 出处**) |
| 加一个知识域(前后端各一处落点) | 前端 `web/src/domains/<域>/` + `domains/index.ts` 加一行;后端 `server/app/services/<域>/` + `services/__init__.py` 加一行 |
| 改某个域的摄取页面 | `web/src/domains/<域>/`(页面、渲染器、module.ts 都在域内,不动共享文件) |
| 加一个跨域/公共页面 | `web/src/pages/` + `web/src/App.tsx` 路由 + `AppLayout`(这是公共契约变更,单独提) |
| 改前端取数 / 错误 toast | `web/src/api/{client,hooks}.ts` |
| 改前端流式渲染 | `web/src/api/sse.ts`(协议出处仍是 `server/app/api/architect.md`) |
| 改对话页行为(会话、气泡、中断) | `web/src/api/useChat.ts` + `web/src/components/{ChatMessages,Composer}.tsx` |
| 改执行轨迹面板 | `web/src/components/TracePanel.tsx` |
| 改任务进度条 | `web/src/components/JobProgress.tsx`(只依赖 Job 框架的四个字段) |
| 改审核台的流程(筛选/批量/键盘/发布) | `web/src/components/StagingReview.tsx`(泛型,不认识 payload) |
| 改某一类知识"通过/驳回"到底做了什么 | 该域的 `actions.ts`(`ReviewActions` 动作层;S1 = 采纳即发布) |
| 改精准问答的上传/校对/文档列表页 | `web/src/domains/exact-qa/`(域内路由在 `IngestPage.tsx`) |
| 改答案上的 Verified 标注与引用展示 | `web/src/components/{ChatMessages,Citations}.tsx` |
| 改上传原件的 PDF 预览出口 | `server/app/api/files.py` 的 `/api/files/documents/{id}/pdf` |
| 改"命中复核关"放不放行的取向 | `server/app/services/exact_qa/retriever.py` 的 `GATE_PROMPT`(改完跑 `smoke_exact_qa.py` 的用例表) |
| 改历史消息要不要带引用/标注 | `server/app/api/conversations.py`(verified 的判定规则只在这一处) |
| 删一份文档要清哪些东西 | S1:`server/app/api/exact_qa.py::delete_document` + `services/exact_qa/storage.py::remove_document_files`;S2 同形状,在 `api/document.py` + `services/document/storage.py` |
| 改 PDF 解析的调用参数 | `server/app/providers/mineru.py::call_mineru`(**C3 已上提到供应商层**,S1 与 S2 共用) |
| 加一类知识的审核界面 | `web/src/domains/<域>/` 写一对渲染器 + 在该域 `module.ts` 的 `renderers` 登记(registry 自动聚合;没登记走 JSON 兜底) |
| 改审核/发布的后端规则 | `server/app/core/staging.py`(状态推导、浅合并、发布状态机) |
| 加一类知识的 publisher(写正式表) | `@register_publisher("qa_pair")`,见 `server/app/core/architect.md` |
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
  上传 ingest_sources → submit_job (Step 7) → BackgroundTasks 派发 execute_job()
    → ingest_jobs(steps 声明式 / progress / step_logs / error,心跳防僵尸)
    → staging_items(待审核)
    → 人工审核 (Step 8):PATCH /api/staging/{id} 单条 / POST /api/staging/bulk 批量
    → POST /api/jobs/{id}/publish:approved+modified 标记 published + 写 publish_records
      └─ 各域 publisher(`register_publisher`)写正式表 + 建索引 —— S1–S3 插进来,S0 是空的
  入口(结构调整后):demo 任务用 curl/脚本提交(旧 JobsPage 已删),轮询 GET /api/jobs/{id};
        失败 → POST /api/jobs/{id}/retry 从失败的那一步重跑;
        跑完 → 浏览器直链 /jobs/{id}/review,<StagingReview> 审 + 发布(qa_pair 走 JSON 兜底渲染);
        正式提交入口由各域开发者在 /ingest/<域> 自己的页面里做
```

## 5. 两个数据库(别搞混)

| 库 | 实例 | 用途 | 账号 | 谁连 |
| --- | --- | --- | --- | --- |
| `agent_system` | `agent_system_pg`(PG16+pgvector,5432) | 本系统全部业务表 | `postgres` | `server/app/db.py` 的 engine |
| `demo_biz` | `agent_system_bizdb`(**MySQL 8.4,3307**) | 演示业务库,问数的查询目标 | `biz_reader`(只读) | `services/text2sql/bizdb.py`,**不共用上面的 engine** |

业务库在 S3 开工时从"同一台 PG 里的另一个 database"改成**独立的 MySQL 容器**
(理由见 `docker/architect.md`:客户库以 MySQL 为多、逼真的 introspection 路径、
物理隔离比 GRANT 更硬)。起法 `make bizdb`,自检 `make bizdb-verify`,进库 `make mysql`。

**各自有哪些表**:`agent_system` 是 DB-DESIGN 里的那些表(§1–§7 分七个域,S3 新增 `datasources` /
`table_meta` / `column_meta` / `relations` / `sql_intents` / `intent_questions` / `non_data_faces` /
`intent_vectors`,废弃 `metrics` / `terms` / `rules` / `sql_examples`);`demo_biz` 是七张
业务表 `products / customers / sales_reps / orders / order_items / inventory / stock_movements`
(**没有 `regions`** —— 州是 customers/sales_reps 上的字段;建表与灌数的唯一出处是 `docker/mysql/`)。
**系统表的结构改动一律先改 DB-DESIGN**;业务库的结构不属于本系统的表结构,它模拟的是客户的库。

## 6. 当前进度

**S0 已完成(Step 1–9,tag `s0-done`)**:仓库骨架 / 30 张表 / 后端骨架 / Provider 抽象层 /
Trace 框架 + 问答链路 / 前端壳 / 对话页 + 通用 Job 框架 / 泛型审核台 + 发布骨架 / 收尾验收。
**S0 的 DoD 已达成**:页面发一句话 → 流式回复 → 右侧看到 trace(阶段/耗时/token/成本)
→ DB 里查得到;假任务提交 → 进度条 → 20 条待审 → 筛选/改/批量/发布 → 审计记录。

`make db && make migrate && make seed && make dev` 之后:

- 页面 http://localhost:5173 —— `/chat` 能真聊天并看执行轨迹,`/agents` 是只读列表,
  `/ingest/exact-qa` 是精准问答的完整流水线(上传 → 校对 → 采纳 → 已发布库,S1 Step 7),
  `/ingest/text2sql` 是问数的治理台(数据源接入 → Schema 治理 → 意图台账与候选审核 →
  意图详情页 `/ingest/text2sql/intents/:id` 的模板验收,D1–D4;问数命中在 `/chat` 里
  显示成结果表格 + 可展开的最终 SQL,D5),
  `/ingest/document` 是文档 RAG 的流水线(上传 PDF → 五步摄取 → 审核台改/合并/不采纳 → 发布成切片),
  `/ingest/workflow` 是编排(第四种知识)的**占位页**:一页静态画布预览,零后端零交互,
  `/how-it-works` 是面试用的说明页(**图先于字**:总页常驻四张图 —— 全局图 / **两级路由图** /
  四种知识的卡片 / 一次请求的判定流程图,其余架构内容进 9 个折叠区,顶部 Expand all 一键全展开;
  **四种知识各有一页**(三层 + `/how-it-works/workflow` 讲编排:概念图 + 四条纪律 +
  客服邮件那条编排逐节点),侧栏里是可展开分组,四页并列;署名在总页页首,零后端依赖),
  `/jobs/{id}/review` 是审核台(直链进入;筛选/改/批量/键盘流/发布),`/styleguide` 是 UI 验收对照页
  (`/kbs`、`/jobs` 页面已删,重定向回 `/chat`;接口与表保留)
- curl 也能直接流式聊天并查 trace:

```bash
curl -N -X POST localhost:8000/api/agents/<agent_id>/chat \
  -H 'Content-Type: application/json' -d '{"question":"..."}'
curl localhost:8000/api/traces/<message_id>
```

契约链路已生效:改后端字段名 → `make types` → 前端 `tsc` 报错(实测见 `web/architect.md`)。

**S0 后做过一次结构调整**(2026-08-21,记录见 `documents/S0-PLAN.md` §5):
前端立了 `web/src/domains/`(DomainModule manifest,加域 = index.ts 加一行),
后端立了 `server/app/services/{exact_qa,document,text2sql}/`(注册解耦到 `services/__init__.py`),
删了 KbListPage / JobsPage / QA 渲染器三个演示页面件。三类 ingestion 的真实流程
**待需求方确认写入 PRD 后**由各域开发者在自己的域文件夹里并行开发,互不打架。

**S1(精准 QA)已闭环**:后端(`services/exact_qa/` 的两个 Job + publisher +
`retrieve_exact_qa` stage + 12 个域接口 + 文件出口)+ 前端四个页面
(`domains/exact-qa/` 的上传/文档列表、校对页、审核台动作层、对话页 Verified 标注)。
Step 8 用一份 4 页虚构业务手册从浏览器走完全程:上传 → 校对(修掉 7 处 MinerU 瑕疵)
→ 抽取 23 条候选 → 采纳 8 条 → 对话命中并原样返回标准答案,刷新后标注仍在。
计划与实施记录见 `documents/S1-PLAN.md`;S0 的见 `documents/S0-PLAN.md`。

**S2(文档 RAG)已闭环到"上传→发布→问答带引用"**(需求 `documents/S2-PRD.md`,
计划与逐段实测证据 `documents/S2-PLAN.md`):沙箱 Step 1–5 逐步调优(解析契约 / 切分 / 三段式图表描述 /
混合检索评测集 31 题),Step 6 把它整体平移进 `server/app/services/document/`,
**三处机械替换**:直调 openai → Provider 层、内存索引 → pgvector、文件与 CLI → Job + 数据库。
一个 Job 五步(parse / clean / chunk / describe / stage)跑完停在审核台;
发布走 `@register_publisher("chunk")`,`chunks` 行与 embedding 同一事务,`tsv` 由生成列自动算。
问答链路上它是**串行兜底的最后一棒**:`retrieve_exact_qa` → `retrieve_text2sql` →
`retrieve_doc_rag` → `generate`(命中时把切片当证据拼进 prompt,答案带 `chunk` 引用,
但**不标 Verified** —— 那句话是模型写的,不是人工采纳过的原文)。
引用**只挂答案正文真正引过的那几条**(编号在拼 prompt 时定死防错位,入选按正文筛);
材料答不了时模型回一句固定的哨兵话术,后端据此落零引用(分册 3 §3b「区分派」)。

**S3(智能问数)已闭环**(计划与逐段证据见 `documents/S3-PLAN.md`,需求见 `documents/S3-PRD.md`):
Phase A/B 已完成并过闸 —— 演示业务库(MySQL)+ 实验床里逐段实测调优的六个 AI 环节
(表列描述 / 意图 / SQL 模板 / 参数区 / 受约束改写 / 意图检索),B8 端到端评测集
**20/20**、越界与拒答硬闸门 7/7。Phase C1–C3 已完成:表结构重审(§4 重写 + 四张新表、
废弃四张旧表)、演示库并入正式 compose 与 bootstrap、B1–B7 代码迁入
`server/app/services/text2sql/`(三个 Job + publisher + 三个冒烟脚本)。
**迁移无损已实测**:同一套 20 题评测集在正式代码路径上 `--check` 与 `--all` 都是 20/20,
终态分布与踩线题与 B 阶段逐项一致。C4/C5 已完成:`api/text2sql.py`(21 条路径 / 29 个操作,
清单在 `server/app/api/architect.md`)+ `core/chat.py` 的 `retrieve_text2sql` stage
(装配在 `services/text2sql/runtime.py`)。**问数三种结局在 chat 里分岔**:执行成功 →
确定性结论 + `sql` 引用(带最终 SQL 与结果表格)并标 Verified;模板外拒答 → 返回理由,
**同样不调生成模型**;非问数 → 检索层零 LLM 判掉后照常走生成。
HTTP 层冒烟 `make smoke-s3-api`(27 步、含 9 条错误路径、不留痕),chat 冒烟
`make smoke-s3-chat`(三问 + trace 五要素 + 零成本断言 + SSE 协议)。
Phase D 已做四页:D1 数据源管理(先测再存 / 只读确认是闸 / 同步进度)、D2 Schema 治理
(左表清单 + 右字段表格,按表保存、单点与批量两个 AI 入口)、D3 意图台账
(批量生成 → 泛型审核台采纳成 draft → 手工新建 → 空路由负例面)、D4 意图详情
(生成模板 → Run → 三区参数 → 相似问法 → 发布),四页都在浏览器走过一遍
(临时资产做完即删;索引面仍是 75 条,评测集复跑仍 20/20)。D3 顺手修了两处"0 条"显示错
(`t2s_intents` 没写 `stats.staged`、共享 `<JobProgress>` 对不产出条目的 Job 也画审核入口);
D4 自测抓出一个后端契约错:`TemplateResult.design` 声明成 `str`,而生成器返回的是结构化
设计说明对象,**任何一次模板生成都 500** —— 新增 `TemplateDesign` 后前端把 join 路径 /
度量口径 / 写死的过滤及其理由摆成了评审面板。
D5 chat 展示(命中 → 结论 + 结果表格 + 可展开可复制的最终 SQL + 踩线提示;trace 五要素)
也在浏览器走过:三个代表问题各问一遍,自测抓出一个用户可见缺陷 —— 模板外拒答显示的是
planner `notes` 的第一条(通常是"日期解析成了几号"这种记账),于是"问利润率"换来一句讲日期的
回答;给理由加了专属字段 `infeasible_reason`(`rewrite.py` 计划 schema),改完 prompt 回评测集
真调 20 题仍 20/20。
**Phase E 已通过**:PRD §7 的七条 DoD 从浏览器按顺序走完 —— 新建只读连接(先测再存)→ 同步 7 表 →
AI 生成 `orders` 的描述并人工改两处 → 四表生成 8 条意图候选、采纳 4 条(**采纳后索引面不变**)→
把其中一条从生成模板、Run 出真数据、手改参数提示词、加相似问法一路做到发布(索引面 75 → 84)→
对话问「How much did we sell in NSW last month?」拿到 `2026-07 / NSW / 7488055.28`(直连 MySQL
核对逐位一致),trace 里看得见改写计划把"last month"解析成 2026-07-01..07-31、最终 SQL 里
`c.state IN ('NSW')` 正是刚手写的提示词被照办 → 再问 profit margin 则给理由拒答、不落生成。
走查抓出一个**共享层**缺陷并修掉:审核台里编辑一条候选并 Save 后,右侧详情会静默换成另一条
(存完就掉出 `pending` 队列,而选中项是"找不到就落第一条"推导的),紧接着点的采纳/驳回会打在
别人身上 —— S1 的审核台同样中招且是采纳即发布,所以修在 `components/StagingReview.tsx`:
**保存不是裁决**,存过未裁决的那一条被钉在列表里。走查后复原(临时数据源与三条 draft 删掉;
`i06` 因为被历史消息的引用指着,按设计只能下线),索引面回到 75、已发布意图 7。
收尾:`make smoke-s3` 20/20、`make smoke-s3-chat` / `make smoke-s3-api` 全绿、`pytest` 84 passed、
`make lint` 全绿;S3 的三份文档(计划 / 需求 / Text2SQL 调研)从 `tmp/` 迁进 `documents/`,
PRD §2.0 / §3.4 / §6 与 §9.6 的 S3 一行按实际回改。
