# web/src/architect.md

## 渲染链

```
main.tsx  createRoot + BrowserRouter + import '@/index.css'
  └─ App.tsx  <Routes>
       └─ AppLayout(唯一的布局路由:侧栏 / 顶栏 / 内容 <Outlet/> / 右侧插槽)
            ├─ /chat        ChatPage      —— useChat(SSE)+ 会话列表,右栏挂 TracePanel
            ├─ /agents      AgentListPage —— GET /api/agents,点行进详情
            ├─ /agents/:id  AgentDetailPage —— GET /api/agents/{id}(含 bindings)
            ├─ /ingest/*    各域 IngestPage —— 遍历 domains/index.ts 的 DOMAINS 生成(空白壳)
            ├─ /jobs/:id/review ReviewPage —— 审核台(入口是直链,任务列表页已删)
            ├─ /settings    SettingsPage  —— GET /healthz
            └─ /styleguide  StyleGuidePage —— 隐藏路由,UI 验收对照
  └─ <Toaster/>  订阅 lib/toast 的 store,渲染在 body 右下角
```

`/` 与未匹配路径都 `Navigate` 到 `/chat`。

## 加一个页面要改哪

- **域内页面**(某类知识的 ingestion 相关):落在 `domains/<域>/`,路由/导航/标题
  由该域 `module.ts` 描述符驱动,共享文件一个都不用改(见 `domains/architect.md`)
- **跨域公共页面**:`pages/XxxPage.tsx`(取数用 `useApi`,三态外壳用 `<DataState>`)+
  `App.tsx` 加 `<Route>` + `layouts/AppLayout.tsx` 的 `NAV_MAIN`/`NAV_FOOT` 与 `TITLES` 各加一行
  —— 这是公共契约变更,不夹在域开发里

## 别名

`@/` → `web/src`(`vite.config.ts` 的 resolve.alias 与 `tsconfig.app.json` 的 paths 两处都要有,
少一处就是"编译过了但运行时找不到"或反过来)。
