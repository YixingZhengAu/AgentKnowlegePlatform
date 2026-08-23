# server/app/api/architect.md

## 约定

- 路径参数一律用 `uuid.UUID` 类型,不要用 `str` ——
  否则非法 uuid 会一路走到 DB,报成 `db_error 503` 而不是 `validation_error 422`
- 找不到资源:`raise NotFoundError(...)`(app/core/errors.py),不要手写 HTTPException
- 需要 DB:形参加 `session: SessionDep`;需要当前用户:`user: CurrentUser`
- 列表排序显式写出来(前端不做二次排序)

## 现有接口的数据来源

- `/healthz`:`SELECT 1` 探活,DB 不通返回 503 + `status="unhealthy"`,**进程不崩**
- `/api/agents/{id}`:agents + agent_kb_bindings JOIN knowledge_bases,按 priority 升序
  (priority 越小越优先,seed 里精准 QA=10 最优先)

## 两个 Step 8 的补充规则

- **`DELETE /api/exact-qa/documents/{id}`**:删文档 = 两个 Job(候选随之级联)+ 文档行 +
  上传原件 + 解析产物目录。**有已发布问答的文档 409 `document_has_published_qa`** ——
  正式 QA 的出处存在候选行的 `origin_ref` 里(`exact_qa_items.source_staging_id` 指过去),
  删了文档,引用里"跳到第 N 页"就悬空。要清这类文档,先逐条下线它的正式 QA。
- **`GET /api/conversations/{id}/messages` 带 `citations` 与 `verified`**:标注不能只活在
  流式那一次的事件里(刷新页面就没了)。`verified` 由后端判定(有 exact_qa 引用即为真),
  规则只写在这一处,前端不猜。引用一次查完再按 message 分组,不做 N+1。

## SSE 事件协议(chat.py)

**S1–S4 只增加事件类型,不改协议**:

```
event: meta         data: {"message_id": "...", "conversation_id": "..."}
event: stage_start  data: {"stage": "retrieve_exact_qa"}          # S1 起,链路的第一个 stage
event: stage_end    data: {"stage": "retrieve_exact_qa", ...}
event: verified     data: {"source": "exact_qa", "score": 0.86,   # ★ S1 新增,仅命中精准 QA 时
                           "matched_question": "...", "citations": [...]}
event: stage_start  data: {"stage": "generate"}                   # 命中时**不会出现**
event: token        data: {"text": "..."}
event: stage_end    data: {"stage": "generate", "seq": 1, "status": "ok",
                           "latency_ms": 812, "model": "gpt-5", "usage": {...}, "cost_usd": "..."}
event: done         data: {"message_id", "conversation_id", "status", "usage",
                           "cost_usd", "latency_ms", "citations": [...], "verified": bool,
                           "trace": [...], "error": null}
event: error        data: {"stage": "generate", "message": "..."}    # 仅失败时
```

**S1 对协议的改动只有"加"**:新增 `verified` 事件、`done` 新增 `verified` 布尔字段、
`citations` 从恒空变成命中时有一条。已有事件的形状一个字没改。

**S3(C5)对协议的改动是零**:它复用同样的事件,只是多了三个 stage 名与一个新的
`verified.source`。Agent 没绑问数库时**一个事件都不多发** —— 只绑精准问答的 Agent,
它的事件流与 S1 时代逐字相同。

```
event: stage_start  data: {"stage": "retrieve_text2sql"}   # 只在 Agent 绑了问数库时出现
event: stage_end    data: {"stage": "retrieve_text2sql", ...}
event: stage_start  data: {"stage": "rewrite_sql"}         # 判成问数才有(唯一一次 LLM 在这)
event: stage_end    data: {"stage": "rewrite_sql", ..., "model": "gpt-5", "usage": {...}}
event: stage_start  data: {"stage": "execute_sql"}         # 计划通过应用器才有
event: stage_end    data: {"stage": "execute_sql", ...}
event: verified     data: {"source": "text2sql", "score": 0.79, "matched_question": "<意图摘要>",
                           "citations": [{"citation_type": "sql", "snippet": "<最终 SQL>",
                                          "extra": {"cols", "rows", "rowcount", "intent_code"}}]}
```

问数三种结局对前端的意义(实测序列见 `scripts/smoke_s3_chat.py`):

| 结局 | 事件上看得到什么 | 有没有 generate |
| --- | --- | --- |
| `executed` | `verified(source=text2sql)` + 一条 `sql` 引用(**带结果表格**,前端不必再请求一次) | **没有** |
| `refused_out_of_template` | 只有 token + done(`verified=false`、无引用),内容是拒答理由 | **没有**(交给它只会换来编数) |
| `refused_non_data` | 三个 stage 里只有 `retrieve_text2sql`,然后照常 generate | 有 |

命中精准 QA 时的事件序列(实测):
`meta → stage_start(retrieve_exact_qa) → stage_end → verified → token → done`
—— **没有 generate 的 stage_start**:命中就原样返回人工采纳过的答案,不调生成模型。
前端据此打 "Verified Answer" 标注:看 `verified` 事件(流式)或 `done.verified`(非流式),
不要自己去猜"是不是只有一个 token 事件"。

`meta` 是对 S0-PLAN 里四个事件的补充:新开会话时前端必须在第一个 token 之前就拿到
conversation_id / message_id,否则没法把这条消息挂到正确的会话上。

三条前端可以依赖的保证:

1. **`done` 是唯一的终止信号**。哪怕编排还没开始就失败(agent 不存在),
   `_sse_stream()` 也会把异常翻译成 `error` + `done`(字段齐全、值为空的 `_ABORTED` 骨架)。
   原因:**流一旦开始,HTTP 状态码就定死 200 了**,再抛异常全局 handler 也改不了,
   客户端只会看到连接莫名断掉。
2. **失败时的兜底话术也走 `token` 事件**:前端只有一条渲染路径,不为失败写第二套。
3. `stream=false` 时同一条链路返回 `ChatResponse`(含 `trace` 数组),字段与 `done` 对齐。

注意:非流式返回体用 `dataclasses.asdict(result)` 构造 —— `ChatResult` 是 slots dataclass,
没有 `__dict__`,`vars()` 会抛 `TypeError`(踩过)。

## 现有接口的数据来源

- `/healthz`:`SELECT 1` 探活,DB 不通返回 503 + `status="unhealthy"`,**进程不崩**
- `/api/agents/{id}`:agents + agent_kb_bindings JOIN knowledge_bases,按 priority 升序
  (priority 越小越优先,seed 里精准 QA=10 最优先)
- `/api/agents/{id}/chat`:`app.core.chat`(编排),自己开 session,不用 `SessionDep`
- `/api/traces/{message_id}`:traces 表按 seq 升序;**消息不存在报 404**,
  "消息存在但没有 trace"返回空数组(两件事要分清)

## 智能问数接口(text2sql.py,C4)

前缀 `/api/text2sql`,21 条路径 / 29 个操作。**候选意图的列表与编辑不在这里** ——
走泛型审核接口(`GET /api/staging?job_id=`、`POST /api/staging/bulk`),
因为"筛选/编辑/批量采纳"对三类知识是同一套流程。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/datasources` | 列表 / 新建(**连接串在这里被 Fernet 加密,明文不再出现在任何地方**) |
| GET/PATCH/DELETE | `/datasources/{id}` | 详情 / 改(传 `conn` 就是整套换掉)/ 删(**挂着意图的 409**) |
| POST | `/datasources/test` | 测**还没保存**的表单(D1 的"先测再存") |
| POST | `/datasources/{id}/test` | 测已保存的;**这是唯一不查 `readonly_confirmed` 的动作** |
| POST | `/datasources/{id}/sync` | 派 `t2s_sync_schema`(零 LLM,随时可重跑) |
| GET | `/datasources/{id}/schema` | 治理页一次拿全:表 + 列 + 采样值 + 枚举字典 + join |
| POST | `/datasources/{id}/describe` | 派 `t2s_describe`(每张启用的表一次 gpt-5) |
| POST | `/datasources/{id}/intents` | 派 `t2s_intents`(候选进审核台,终态 `review`) |
| PUT | `/tables/{id}` | **按表保存**:表级字段 + 若干列,一个事务;跨表改列 409 |
| POST | `/tables/{id}/describe` | 单点 AI 生成描述,**同步返回建议、不落库** |
| GET/POST | `/intents` | 列表(可按 status)/ 手工新建(建出来是 **draft**) |
| GET/PATCH/DELETE | `/intents/{id}` | 详情(含三区参数 + `publish_blockers`)/ 就地编辑 / 删(**只许删 draft**) |
| POST | `/intents/{id}/template` | ★ B4+B5 全链路,**同步**(慢且贵),返回时 SQL 已在真库跑出过非空结果;`design` 是**结构化**设计说明(`TemplateDesign`:join 路径 / 度量 / 写死的过滤及其理由),不是一段文字 |
| POST | `/intents/{id}/parse-params` | 按当前 SQL 重解析参数区(纯代码,零 LLM),按 param_id 保住已写的 hint |
| POST | `/intents/{id}/run` | ★ 走**运行时那道执行闸**;被闸拒是 `ok=false`,不是 4xx |
| POST | `/intents/{id}/publish` | 校验 → published → 重建索引面(意图的 + 本 kb 的空路由面) |
| POST | `/intents/{id}/disable` | disabled + 删索引面;**正式行留着**(历史引用不能悬空) |
| GET | `/intents/{id}/questions` | 相似问法 |
| POST | `/intents/{id}/questions/generate` | AI 生成建议(未落库),带 `dropped` 与被丢弃的理由 |
| PUT | `/intents/{id}/questions` | 整组替换 + **保存即重建索引面** |
| GET/PUT | `/non-data-faces` | 空路由负例面(整组替换,保存即重建);清空 = 关掉空路由 |
| GET | `/index-stats` | 各类面各有多少(`summary + question + non_data` 就是检索的全部输入) |

四条规则,每条都在拦一类真实事故:

1. **口令进不出**。入参收到明文立刻加密落库,任何出参只回 host/port/user/database。
   冒烟脚本对此有断言(断的是 `user:pass@` 这个泄漏形态)。
2. **要连客户库的动作都先查 `readonly_confirmed`**,不过就 409 `datasource_not_readonly`
   —— 这不是提示,是拒:可写账号接进来,四道安全关就少了最硬的那一道。测连是唯一例外。
3. **贵的活分两种**:批量(每表一次 gpt-5)一律派 Job 让页面可以离开,单点(一条模板)
   同步返回。Job 的 `params` 里**只放 `datasource_id`** —— 它会落库、会出接口。
4. **"连不上"和"SQL 写错了"是业务结果,不是接口错误**:`/datasources/test` 与
   `/intents/{id}/run` 失败都返回 200 + `ok=false` + 原因。前端在表单/编辑器里显示红字,
   不用去解析错误码。

冒烟:`make smoke-s3-api`(27 步,含 9 条错误路径;**不留痕** —— 建的临时数据源与草稿
意图会删掉、下线的意图重新发布、索引面回到原数,所以跑完 `make smoke-s3` 的评测集
分数一个字不变)。

## 摄取 Job 接口(jobs.py)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/jobs` | 列表(可按 `kb_id` / `status` 过滤,默认 50 条,按创建时间倒序) |
| GET | `/api/jobs/types` | 已注册的 job_type(前端下拉框用它,不硬编码) |
| POST | `/api/jobs` | 提交:`{job_type, kb_id, source_id?, params}` → 201 + JobOut |
| GET | `/api/jobs/{id}` | 进度查询(前端轮询这个);顺便做心跳超时的惰性僵尸判定 |
| POST | `/api/jobs/{id}/retry` | 从失败的那一步重跑(只有 `status=failed` 能重跑,否则 409) |

**Job 注册链**:`jobs.py` 只 `import app.services`(noqa 副作用 import),
具体任务在 `services/__init__.py` 里注册 —— api 层不认识任何具体域(结构调整 Stage 3)。

**路由顺序有讲究**:`/api/jobs/types` 必须声明在 `/api/jobs/{job_id}` 之前,
否则 `types` 会被当成 uuid 参数吃掉(422)。

派发用 **FastAPI BackgroundTasks**:响应发出去之后才开始跑,所以提交是瞬时返回的。
代价是"进程重启 = 任务丢失",补偿在 `core/jobs.py`(启动收尸 + 心跳超时),
保证任务不会永远停在 running。

`POST /api/jobs` 会先检查 kb 是否存在 —— 不拦的话会撞外键、报成 `db_error 503`,
把"知识库 id 写错了"这个真实原因盖住。

## 待审内容与发布接口(staging.py + jobs.py)

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/staging?job_id=&review_status=&item_type=&sort=&limit=` | 一批待审内容;`sort` 默认 `confidence_asc`(最不靠谱的先看) |
| GET | `/api/staging/summary?job_id=` | 按 review_status 计数 + 已发布数(审核台筛选标签用) |
| PATCH | `/api/staging/{id}` | 审一条:`{payload?, review_status?, review_note?}`;只传 payload = `modified` |
| POST | `/api/staging/bulk` | 批量:`{ids, review_status}` → `{updated}` |
| POST | `/api/jobs/{id}/publish` | 发布:approved/modified 标记 published + 写 `publish_records` |

**为什么按 `job_id` 查而不是 `kb_id`**:一次审核就是"审这一批加工产物"。
按 KB 查会把历史所有批次混在一起,审到一半分不清哪条是这次抽出来的。

**发布挂在 jobs 下**:发布是**一个 job 的**动作(整批一起发、写一条审计),
不是某条 item 的动作,路由位置要说明这件事。

三个会遇到的 409(都在后端拦,不靠前端禁用按钮):
`job_not_publishable`(重复发布)/ `nothing_to_publish`(一条都没通过)/
`job_not_reviewable`(发布之后又来审)。

**校验正则必须锚定**:`pattern="|".join(...)` 不加 `^$` 的话 `xapprovedy` 也算合法,
错值一路走到 DB 的 CHECK 才被拦(报成 500,而不是 422)。

## 待加(后续 Step)

- S1 起:`POST /api/ingest/sources`(上传原料)、各类型的 publisher 注册
