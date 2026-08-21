# web/src/layouts/architect.md

## 布局结构

```
<div flex h-screen>
  <nav 220px bg-primary>      侧栏:激活项左侧 3px 黄竖条 + bg-white/8
  <div flex-1 flex-col>
    <header 56px bg-card>     顶栏:页面标题 + (有右栏时)显示/隐藏按钮
    <div flex flex-1>
      <main flex-1 overflow-y-auto p-6>  <Outlet/>
      <aside 360px bg-card>              右侧插槽(仅当页面塞了内容且未折叠)
```

## 右侧面板插槽的实现

`RightPanelContext` 只暴露一个 `setPanel`;页面用 `useRightPanel(title, node, deps)`:
effect 里 set,卸载 return 里清空。**没有内容时整个 `<aside>` 不渲染** ——
列表页不该白让出 360px,而对话页一进去就该看到"轨迹会出现在这里"。

`useMemo(() => ({setPanel}), [])` 固定 context 值,避免布局重渲染把所有页面拖着重跑 effect。

## 改导航要动两处

`NAV_MAIN`/`NAV_FOOT`(侧栏条目,含 lucide 图标)和 `TITLES`(路径前缀 → 顶栏标题)。
当前顶级项:Chat / Agents / Knowledge Ingestion(可展开分组)/ Settings。
分组子项与各域顶栏标题**遍历 `domains/index.ts` 的 DOMAINS 生成**,本文件不硬编码任何域;
子项用识别色圆点(`toneClass`,色值只在 index.css)。分组展开态:落在 `/ingest/*` 上默认展开。
`TITLES` 用 find 按前缀匹配,更具体的前缀(如 `/jobs/`)排前面。
隐藏路由(如 `/styleguide`)只进 `TITLES` 不进导航。
