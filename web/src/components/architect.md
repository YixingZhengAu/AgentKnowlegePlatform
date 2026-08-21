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

## StagingReview:泛型审核台

```
[筛选标签 + 计数 | 排序 | Publish(唯一黄色 CTA)]
[列表 380px:48px 行 + 勾选 + 置信度徽标 + 状态点]  [编辑区:渲染器 + 溯源 + 动作条]
[勾选后吸底的批量操作栏]
```

它**不认识**待审内容是什么:payload 交给传进来的渲染器画(见 `staging/`),
自己只负责流程 —— 筛选 / 排序 / 单条通过驳回改 / 批量 / 键盘流 / 发布。
所以 S1/S2/S3 的审核界面 = 写两个渲染器 + 在注册表加一行。

**四个刻意的设计决定**:

1. **默认按置信度升序**(`sort=confidence_asc`):最不靠谱的排最前。审核的时间应该
   花在最可能出错的地方 —— 这也是抽取任务给每条打 confidence 的唯一用途。
2. **选中项是推导出来的,不是一个状态**:`selectedId` 在当前列表里找不到就落到第一条。
   于是筛选变化、条目审完消失都不需要 effect 去同步选中态(effect 里同步 setState
   既多一轮渲染,新版 react-hooks 规则也直接报 error)。
3. **草稿按 id 记**(`draft = {id, payload}`):切条目时旧草稿自动失效,不用 effect 清理。
   通过时如果有未保存的改动就一起带上 —— 审到一半改了内容再点通过,不该丢改动。
4. **发布成功立刻置只读**(`justPublished`):等 job 状态那次往返期间,界面不该还允许
   "通过"(那一条通过了也永远发不出去)。后端还有一道 `job_not_reviewable` 兜底。

**计数从 `/api/staging/summary` 来,不在前端数**:前端只有当前筛选下的条目,数不准。

**键盘流**:`j/k` 走条目、`a` 通过(自动跳下一条)、`x` 驳回、空格勾选。
监听在 window 上,先判断事件目标是不是 INPUT/TEXTAREA/SELECT ——
在输入框里按 a 当然应该是打字。

## Toaster:为什么不装库

全站只需要"失败弹一条"这一种行为。`lib/toast.ts` 是模块级 store(数组 + 订阅集合),
组件用 `useSyncExternalStore` 读 —— 40 行,零依赖,不跟设计 token 打架。
