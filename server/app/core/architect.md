# server/app/core/architect.md

## 统一错误体

对外固定格式,前端只认这一种:

```json
{"error": {"code": "not_found", "message": "...", "detail": null}}
```

异常类 -> 状态码 / code:

| 异常 | 状态码 | code |
| --- | --- | --- |
| `NotFoundError` | 404 | not_found |
| `ConflictError` | 409 | conflict |
| `ConfigError` | 500 | config_error |
| `ProviderError` | 502 | provider_error |
| `RequestValidationError` | 422 | validation_error |
| `SQLAlchemyError` | 503 | db_error |
| `ConnectionError` | 503 | db_error |
| 其他 | 500 | internal_error(带 request_id) |

**为什么单列 `ConnectionError`**:连不上 Postgres 时 asyncpg 抛的是裸
`ConnectionRefusedError`(OSError 子类),SQLAlchemy 不包装它 —— 不单独接住就会报成
internal_error,掩盖"数据库没起"这个真实原因。

## 日志

- `request_id_ctx`(ContextVar)由中间件写入,`_add_request_id` 处理器给每条日志附加
- dev 用 `ConsoleRenderer`(彩色),prod 用 `JSONRenderer`
- `uvicorn.access` 被禁用,访问日志由 `RequestContextMiddleware` 输出;`/healthz` 不记(降噪)

## Trace 框架(trace.py)

三条原则:**失败也落库**(`status=error` 的 trace 比成功的有价值)、**不阻塞主链路**
(先攒在 `ChatContext.spans`,问答结束一次批量插入)、**只存摘要**(`summarize()` 统一截断
长字符串到 1000 字符、列表最多 20 项 —— trace 是给人看"发生了什么",全文在 messages/chunks 里)。

```python
async with traced(ctx, "generate", input={...}) as span:
    result = await llm.complete(...)
    span.output = {"text": result.text}
    span.record_llm(result)      # 一行带走 model / usage / cost
```

- `ChatContext`:一次问答的所有 stage 共享同一个 `message_id`(助手消息 id,**预生成**)
- `traced()` 进入时就把 span 挂进 `ctx.spans`,所以异常路径也不会漏记
- `flush_traces(session, ctx)` 只 `add_all`,commit 由调用方做;
  **调用前助手消息必须已落库**(`traces.message_id` 外键指向它)
- `spans_as_dicts()` 是给 SSE / 非流式返回体用的轻量表示

## 问答编排(chat.py)

**单入口是怎么做到的**:真正的编排只有 async generator `chat_events()`,永远产出事件流;
`run_chat()` 只是把它消费到底拼成 `ChatResult`(S6 评测执行器用这个)。
流式与非流式共用一份代码,S1–S4 插阶段不可能只改到一边(D4)。

S1 + S3 链路:

```
加载 agent → 存用户消息(先 commit)→ [stage: retrieve_exact_qa]
   ├─ HIT       → 原样返回标准答案 + 写 message_citations + verified 事件,**不调生成模型**
   └─ 其他       → [stage: retrieve_text2sql](Agent 绑了问数库才跑,没绑一个事件都不发)
                     ├─ executed                 → 确定性结论 + sql 引用(SQL+表格),标 verified
                     ├─ refused_out_of_template   → 返回拒答理由,**也不调生成模型**
                     └─ refused_non_data / 出错   → [stage: generate] 调 LLM
→ 存助手消息(+ citations)→ flush traces
```

★ **命中即短路**是零幻觉承诺的落地点:答案是人工采纳过的原文,不让模型碰它,
连润色都不做 —— 一旦过生成模型,"已验证"这个标注就不成立了。机器可证明的形式是
"trace 里没有 generate 这个 stage"(`scripts/smoke_s1_chat.py` 就是这么断言的)。

检索 stage 的三条纪律:

- **检索失败不许弄死问答**:`retrieve_exact_qa` 整段包在 try/except 里,
  异常退化成"没命中",照常走生成(库挂了不该让对话页变白屏)
- **BORDERLINE 也要留 trace**:分数 + 命中面 + 是哪道关否决的(护栏差集 / 复核理由),
  这是后续调阈值的唯一依据(见 `chat.py::_retrieval_trace`)
- light 模型复核的 usage 也 `span.record_llm()`,否则那 2.9s 和几分钱是黑账

问数 stage 的四条(C5):

- **两种拒答分岔是刻意的**:模板外拒答(问对了域、超出了已验收模板)**不交给生成模型**
  —— 那只会换来一个听起来合理的编数,而这是问数链路最不能出的错;非问数拒答
  (检索层零 LLM 就判掉了)本来就该由别的链路接手,所以照常走生成。
- **`execution_failed` 永远算 bug**,不是业务边界:`log.error` + 一个 `error` 事件,
  然后退回生成(让整条问答挂掉更糟)。它出现在日志里就该有人去看。
- **编排不在这里**:三个 stage 的内容来自 `pipeline.answer()`(被评测集守着的代码),
  这里只负责把它摊成 span —— 埋点字段的唯一出处是 `pipeline.trace_events()`。
  两件必须自己动手的事写在 `chat.py::_t2s_spans` 的 docstring 里:把
  `retrieve_text2sql` 的耗时改成"只有检索那一段"(否则 `total_latency_ms` 会翻倍),
  以及把 LLM 的账记在 `rewrite_sql` 上(唯一一次模型调用是改写计划)。
- **非问数问题的 `rewrite_sql` span 不存在,于是也没有账** —— 那就是"检索层拒答
  零成本"的机器可证形式(`scripts/smoke_s3_chat.py` 就是这么断言的)。

S4 插 `route` 同理:加一个 `async with traced(...)` 块,事件协议只增不改。

四个已经踩过/想清楚的点:

1. **用户消息先单独 commit**:生成失败也不能丢掉用户的问题(未命中问题池要用它)。
2. **助手消息 id 预生成**:trace 要在 message 存在后才能插,先生成 uuid 才能让
   `meta` 事件在第一个 token 之前就把 message_id 交给前端。
3. **`stage_end` 不能放在 `finally` 里 yield**:客户端断开时 finally 里 yield 会变成
   `RuntimeError: async generator ignored GeneratorExit`。放在 try/except 之后。
4. **中断落库要 detach**:捕获 `GeneratorExit / CancelledError` 后当前任务正在被取消,
   **再 await 会立刻又被取消**。所以 `_persist()` 自己开 session,中断路径用
   `_detach()` 丢到后台任务里跑(`_BACKGROUND` 持引用防 GC),消息按
   `status="interrupted"` 落库。不这么做 DB 里只剩一条用户提问、没有任何助手消息和 trace。

会话:不传 `conversation_id` 就新开一轮(标题取首问前 60 字);历史带最近
`HISTORY_LIMIT=10` 条,**只带 `status=completed` 的消息**(失败/中断的不进 prompt)。

## Job 框架(jobs.py + jobs_demo.py)

三类知识的摄取业务完全不同,但"分步执行 / 报进度 / 分步日志 / 失败可从该步重跑 /
前端一个进度条通吃"这套骨架完全一样。所以框架在这里,S1–S3 只贡献子类。

子类要写的只有两样:

```python
@register_job
class QaExtractJob(JobRunner):
    job_type = "qa_extract"
    steps = [JobStepDef("parse", "Parse source"), JobStepDef("extract", "Extract QA pairs")]

    async def prepare(self, ctx): ...           # 重跑也会执行,必须幂等
    async def step_parse(self, ctx): ...        # 返回值 = 这一步的日志 message
    async def step_extract(self, ctx): ...
```

| 函数 | 职责 |
| --- | --- |
| `submit_job()` | 建 `ingest_jobs` 行(status=queued,**steps 骨架现在就写进去**)并返回 |
| `execute_job(job_id, from_step=None)` | 逐步执行;**永不抛异常**,失败写进 `error` |
| `retry_job(job_id)` | 校验状态(只有 failed 能重跑)+ 定位起点步骤,返回给调用方派发 |
| `reap_abandoned_jobs()` | 启动时收尸:`running`/`publishing` 一律判 failed |
| `fail_if_stalled(job, session)` | 惰性判定:心跳停超 `JOB_HEARTBEAT_TIMEOUT_SEC` 就判 failed |

**四个刻意的设计决定**:

1. **步骤是数据不是代码流程**(`steps` 声明式)。所以任务还没开始跑,前端就能画出
   全部步骤 —— 用户看到"四步里的第二步",而不是"日志冒了两行"。
2. **每次写库都自己开一个短 session**。Job 可能跑几分钟,不能借请求作用域的 session
   (请求早就结束了)。JSONB 里的 list **不能就地 append**(SQLAlchemy 检测不到),
   `_append_log()` 整体重新赋值。
3. **僵尸任务两道防线**。执行器是进程内 BackgroundTasks(刻意不上 Celery),
   进程一重启内存里的任务就没了 —— 所以启动这一刻还标着 running 的**一定**是僵尸,
   `reap_abandoned_jobs()` 可以武断地全判失败;而"进程活着但协程死了"这种情况
   抓不到,靠心跳超时在查询接口里惰性判定(`fail_if_stalled`)。
   没有这两道,kill 一次后端就会留下一个永远 99% 的任务。
4. **失败步骤名留在 `current_step` 上**,重跑接口就是从它开始的;历史日志不清空,
   只追加一行 `status=info` 的 Retry 分隔 —— "重跑过"这件事本身是审计信息。

## 审核与发布骨架(staging.py)

Job 把加工产物写进 `staging_items`,人过一眼,再发布进正式表。三类知识的**内容**不同,
但"通过/驳回/改一改 → 点发布 → 留一条审计"这套**流程**一样,所以流程在这里写一遍。

| 函数 | 职责 |
| --- | --- |
| `merge_payload(old, patch)` | payload 的 PATCH 语义:**顶层键浅合并**,list 整份替换 |
| `derive_review_status(...)` | 状态推导:显式传的赢 → 只改了内容 = `modified` → 否则保持 |
| `assert_reviewable(session, job_id)` | 审核动作的闸:只有 `review` 的 job 能审 |
| `patch_item(...)` | 审一条:改内容 / 改状态 / 加备注 + 写 `reviewed_by/at` |
| `bulk_review(...)` | 批量通过驳回;已发布的条目静默跳过,不打断整批 |
| `summarize(session, job_id)` | 按 review_status 计数(审核台顶部的筛选标签渲染它) |
| `publish_job(session, job_id)` | `review → publishing → published`,写 `publish_records` |
| `register_publisher(item_type)` | **扩展点**:各类型"写正式表 + 建索引"在这里插进来 |

**三个刻意的设计决定**:

1. **S0 只做通用部分**。发布 = 标记 `published` + 写审计;`published_ref` 是 null
   不是漏了 —— 这一层不该知道 `exact_qa_items` 长什么样。S1 注册一个 publisher 就补上了。
2. **`modified` 也发布**。"人工改过再通过"如果不算通过,改完的条目永远发不出去。
3. **审核有前置状态闸**。发布之后再"通过"一条,那条永远发不出去(job 已是 published,
   发布接口不再受理)—— 所以 `patch_item` / `bulk_review` 都先过 `assert_reviewable`,
   界面上的只读只是提示,这里才是防线。

**状态推导为什么值得单独一个函数**:前端也需要知道"改了内容会变成 modified",
但这个规则只能有一处出处。做成纯函数后它可以离线测(`tests/test_staging.py`),
前端则完全不用重复这套逻辑 —— 它只管把改动发上来,状态由后端定。

`DemoSleepJob`(jobs_demo.py)是验证框架用的假任务:四步、每步睡 `step_seconds`、
最后写 `items` 条 `staging_items`(Step 8 审核台的素材)。`fail_at` 参数让指定步骤
**只失败一次** —— 重跑时框架发现这步已经有一条 error 日志就放它过去,
否则"重试"按钮永远重试失败,演示不出恢复路径。

## 待加(后续 Step)

- Step 8:staging 审核与发布的通用骨架(publisher 由 S1–S3 各自实现)
