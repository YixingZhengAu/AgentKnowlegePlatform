# web/src/components/architect.md

## 谁该放这里

跨页面复用、且不含某个页面业务假设的组件。只有一个页面用的东西留在那个页面文件里。

## StatusBadge:状态色的单点映射

后端有多套状态字符串(消息 `completed/failed/interrupted`、审核 `approved/rejected/edited`、
trace `ok/error`、KB `active/archived`)。它们的颜色规则在 UI-STYLE §2 是同一套语义,
所以只在 `StatusBadge.tsx` 的 `TONE` 里映射一次。**新状态值加在那张表里,不要在页面里写颜色**。

## DataState:三态不各写一遍

```tsx
<DataState state={useApi(...)} isEmpty={d => d.items.length === 0}
           emptyIcon={Library} emptyTitle="No knowledge bases yet">
  {(data) => <Table>…</Table>}
</DataState>
```

- loading 且还没有旧数据 → 骨架;有旧数据时不闪(reload 场景)
- error → 显示后端的 `code` 作标题、`message` 作正文 + Retry 按钮(截图就能定位问题)
- 错误已经在 `useApi` 里弹过 toast,这里是页面内的常驻态,两者不冲突

## Toaster:为什么不装库

全站只需要"失败弹一条"这一种行为。`lib/toast.ts` 是模块级 store(数组 + 订阅集合),
组件用 `useSyncExternalStore` 读 —— 40 行,零依赖,不跟设计 token 打架。
