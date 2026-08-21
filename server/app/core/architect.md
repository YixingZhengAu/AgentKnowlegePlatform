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

S0 链路:`加载 agent → 存用户消息(先 commit)→ [stage: generate] → 存助手消息 → flush traces`。
没有检索、没有路由;S1 在 generate 前插 `retrieve_exact_qa`,S4 插 `route`,事件协议不变。

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

`DemoSleepJob`(jobs_demo.py)是验证框架用的假任务:四步、每步睡 `step_seconds`、
最后写 `items` 条 `staging_items`(Step 8 审核台的素材)。`fail_at` 参数让指定步骤
**只失败一次** —— 重跑时框架发现这步已经有一条 error 日志就放它过去,
否则"重试"按钮永远重试失败,演示不出恢复路径。

## 待加(后续 Step)

- Step 8:staging 审核与发布的通用骨架(publisher 由 S1–S3 各自实现)
