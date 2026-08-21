# web/src/architect.md

## 渲染链

```
main.tsx  createRoot + BrowserRouter + import '@/index.css'
  └─ App.tsx  <Routes>
       └─ AppLayout(唯一的布局路由:侧栏 / 顶栏 / 内容 <Outlet/> / 右侧插槽)
            ├─ /chat        ChatPage      —— useChat(SSE)+ 会话列表,右栏挂 TracePanel
            ├─ /kbs         KbListPage    —— GET /api/kbs
            ├─ /agents      AgentListPage —— GET /api/agents,点行进详情
            ├─ /agents/:id  AgentDetailPage —— GET /api/agents/{id}(含 bindings)
            ├─ /jobs        JobsPage      —— POST/GET /api/jobs,右栏挂 JobProgress
            ├─ /settings    SettingsPage  —— GET /healthz
            └─ /styleguide  StyleGuidePage —— 隐藏路由,UI 验收对照
  └─ <Toaster/>  订阅 lib/toast 的 store,渲染在 body 右下角
```

`/` 与未匹配路径都 `Navigate` 到 `/chat`。

## 加一个页面要改哪

1. `pages/XxxPage.tsx`(取数用 `useApi`,三态外壳用 `<DataState>`)
2. `App.tsx` 加一条 `<Route>`
3. `layouts/AppLayout.tsx` 的 `NAV`(要进侧栏)与 `TITLES`(顶栏标题)各加一行

## 别名

`@/` → `web/src`(`vite.config.ts` 的 resolve.alias 与 `tsconfig.app.json` 的 paths 两处都要有,
少一处就是"编译过了但运行时找不到"或反过来)。
