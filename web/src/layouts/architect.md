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

`NAV`(侧栏条目,含 lucide 图标)和 `TITLES`(路径前缀 → 顶栏标题)。
隐藏路由(如 `/styleguide`)只进 `TITLES` 不进 `NAV`。
