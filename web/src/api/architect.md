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

Step 7 加 Job 轮询就在这里加 `refetchInterval`,不换实现。

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
- 用 `.ts` 后缀 import `./client.ts`:Node 原生跑 TS 时不做扩展名补全(Vite 两种都认)

## schema.ts

`KB_TYPE_LABEL` / `KB_TYPE_DOT` 的 key 取值与 `server/app/models/knowledge.py` 的
`KB_TYPES`(`exact_qa` / `document` / `text2sql`)一致 —— 注意是 `document` 而不是 `doc_rag`。
识别色用**固定映射**而不是拼 class 名:Tailwind 扫源码生成类,拼出来的类名不会被生成。
