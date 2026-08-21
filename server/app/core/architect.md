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

## 待加(后续 Step)

- Step 7:`jobs.py`(`submit_job()` + 执行器基类 + 僵尸任务清理)
