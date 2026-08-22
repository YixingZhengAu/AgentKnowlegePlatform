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
