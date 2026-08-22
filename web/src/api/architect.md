# web/src/api/architect.md

## client.ts

- `API_BASE = import.meta.env?.VITE_API_BASE ?? ''` —— 默认同源走 Vite 代理。
  可选链不是多余的:`scripts/smoke_sse.ts` 用 Node 原生跑这份文件,那边没有 Vite 注入的 env。
- `toApiError(res)`:响应体读不出来也要给人话(不能只剩一个状态码)
- 网络层失败(后端没起)翻成 `code=network_error`,而不是让界面上出现裸的 "Failed to fetch"

## hooks.ts

`loading` 由 `result.key !== key` 推导,**不在 effect 里同步 setState**
(新版 `eslint-plugin-react-hooks` 直接报 error:`set-state-in-effect`)。
`reload()` 靠 `tick` 自增改变 key。切页/换 path 时用 `cancelled` 闭包标记丢弃回包。

两个 Step 7 加上来的能力:

- **`path` 可以是 `null`** = 这次不取数(hook 不能条件调用,但"暂时没有 id 可查"是常态,
  比如 trace 面板还没有 message_id)。比造一个假 path 干净。
- **`refetchInterval` 可以是一个读当前数据的函数**:
  `refetchInterval: (job) => (isJobActive(job?.status) ? 1000 : null)`。
  为什么必须是函数 —— "任务到终态就停轮询"这个判断得看到刚拿回来的数据,
  写成常量的话它要在调用 useApi 之前算出来,那时数据还没回来。
  effect 的依赖里放的是**算出来的数字**,所以每次渲染传新函数也不会重装定时器。

## useChat.ts

一次问答期间有五件事同时在变(助手消息内容、当前 stage、trace 列表、会话 id、错误),
放在一个 hook 里才说得清。两个关键决定:

1. **历史消息是"点了才取",没有 effect 盯着 conversationId 自动取。**
   新会话的 id 是后端在流的第一个事件(`meta`)里给的;如果有 effect 跟着它自动拉历史,
   会在流还没结束时把正在流的消息覆盖掉。所以取数只发生在用户点会话那一刻。
2. **助手消息的 id 用后端的 `message_id`**(先用本地占位 id,`meta` 到达时替换)。
   流完之后右侧面板要查 `GET /api/traces/{id}`,不用另找 id。

`done` 事件里成本是独立字段,但落库时是塞进 `usage` 的(见 `core/chat.py` 的 `_persist`),
所以 `onDone` 会把它合并进 `usage` —— 刚答完的消息与从库里读回的历史消息形状一致。

中断:`stop()` abort 掉 fetch,后端按 `status="interrupted"` 落库,前端把气泡标成 interrupted。

## sse.ts

```
streamChat({agentId, question, conversationId, handlers, signal}) -> Promise<ChatResponse>
  fetch POST /api/agents/{id}/chat  {stream:true}
    ├─ 非 2xx / 没有 body → toApiError 抛出(流还没开始的失败:422、503)
    └─ body.pipeThrough(TextDecoderStream) → 按 /\r?\n\r?\n/ 切帧 → parseSseFrame → dispatch
         meta / stage_start / token / stage_end / error / done  → handlers.onXxx
    收不到 done → 抛 stream_incomplete(绝不静默当成功)
```

- 事件协议出处是 `server/app/api/architect.md`,改协议前后端一起改
- `dispatch()` 的 switch **不写 default 抛错**:S1–S4 会加新事件类型,老前端必须容忍
- S1 加了一个 `verified` 事件(命中精准问答:答案是库里原话,且**没有 generate 阶段**)。
  前端认标注只看 `verified` 事件 / `done.verified`,不去猜"是不是只有一个 token"
- `citations` **是生成类型**(后端 `MessageCitationOut` + `CitationExtra`,Step 8 从裸 dict
  改成真 schema);`schema.ts` 的 `MessageCitation` 只是取个短名,不再是手写的约定型
- 历史消息也带 `citations` 与 `verified`(`GET /messages`),所以刷新页面标注不会丢 ——
  前端不自己推 verified,后端一处判定
- 用 `.ts` 后缀 import `./client.ts`:Node 原生跑 TS 时不做扩展名补全(Vite 两种都认)

## schema.ts

`KB_TYPE_LABEL` / `KB_TYPE_DOT` 的 key 取值与 `server/app/models/knowledge.py` 的
`KB_TYPES`(`exact_qa` / `document` / `text2sql`)一致 —— 注意是 `document` 而不是 `doc_rag`。
识别色用**固定映射**而不是拼 class 名:Tailwind 扫源码生成类,拼出来的类名不会被生成。
