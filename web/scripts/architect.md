# web/scripts/architect.md

## smoke_sse.ts 为什么这么写

- **import 产线代码而不是复制解析逻辑**:要验的是 `src/api/sse.ts` 里那份帧解析与事件分派;
  抄一份到脚本里就等于验了个假的
- Node 24 原生跑 `.ts`(只做类型擦除),所以产线代码里不能出现 enum / namespace 这类
  不可擦除语法(`tsconfig` 已开 `erasableSyntaxOnly` 兜住),
  且相对 import 要带 `.ts` 后缀(Node 不做扩展名补全)
- 脚本里给 `globalThis.fetch` 打了一层前缀补全:产线代码用相对路径(浏览器里同源),
  Node 里没有 origin,所以把 `/api/...` 补成 `${API_BASE}/api/...`
- 断言四件事:事件顺序 `meta → stage_start → token → stage_end → done`、
  至少一个 token、拼出来的回答非空、`done.status === 'completed'` 且带 trace

## 两种跑法的区别

| 命令 | 验什么 |
| --- | --- |
| `npm run smoke:sse` | 直连 8000:后端 SSE 协议 + 前端解析 |
| `API_BASE=http://localhost:5173 npm run smoke:sse` | 穿 Vite 代理:**代理会不会把流缓冲住**(浏览器实际走这条路) |
