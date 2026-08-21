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

## TracePanel:两种数据来源,一套渲染

| 场景 | 来源 | 有什么 |
| --- | --- | --- |
| 正在流 / 刚答完 | SSE 的 `stage_end` 事件(`useChat` 累积) | 阶段、耗时、token、成本 |
| 点开历史消息 | `GET /api/traces/{message_id}` | 上面全部 + input/output 摘要,可展开 |

两种来源用 `fromSpan()` / `fromTrace()` 归一成 `TraceRow`,渲染只写一遍。
流还在跑时**不查接口**(trace 要等助手消息落库之后才存在),这期间显示当前阶段的脉冲行。
行的 `key` 里带 messageId:阶段名和 seq 在不同消息里会重复,不带的话展开状态会串。

## JobProgress:只依赖 Job 框架的四个字段

`steps` / `progress` / `step_logs` / `error` —— 与 `job_type` 无关,所以 S1/S2/S3 的摄取
进度都用它。每一步"现在什么状态"由 `stepState()` 从声明的步骤 + 已有日志推导
(done / failed / running / pending),后端不用为此多给字段。

轮询到终态自动停;重跑后状态回到 queued,轮询自己就恢复了 —— 不需要额外的开关状态。

## Toaster:为什么不装库

全站只需要"失败弹一条"这一种行为。`lib/toast.ts` 是模块级 store(数组 + 订阅集合),
组件用 `useSyncExternalStore` 读 —— 40 行,零依赖,不跟设计 token 打架。
