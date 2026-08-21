# web/src/pages/architect.md

## 页面的统一写法

```tsx
const state = useApi<KbList>('/api/kbs')          // 三态在 hook 里
<Card><CardHeader>…</CardHeader>
  <DataState state={state} isEmpty={…} emptyIcon={…} emptyTitle="…">
    {(data) => <Table>…</Table>}
  </DataState>
</Card>
```

卡片标题**不要跟顶栏标题重复**(顶栏已经写了 "Knowledge Bases",卡片就叫 "Governance tiers")。

## ChatPage:三块拼起来

```
[会话列表 240px] [消息流 + 输入框] │ 右侧面板挂 <TracePanel>(AppLayout 的插槽)
```

- **"新对话"没有对应的接口**:后端不传 `conversation_id` 就等于新开一轮,
  所以点 New chat 只是清空本地状态 —— 少一次往返,也不留"建了但没发消息"的空会话。
- 删除是软删(`DELETE /api/conversations/{id}` → status=archived),消息与 trace 都留着。
- 右侧面板默认盯最后一条助手消息;点某条气泡就切到那条(历史消息会去查完整 trace)。
- 流结束后再刷一次会话列表:标题与 `last_message_at` 是后端在这一轮里写的。

## JobsPage:假任务的联调界面

S0 只有 `demo_sleep`,但这页的形状就是 S1–S3 摄取的形状:
选知识库 → 提交 → 右侧看进度与分步日志 → 失败了从失败步骤重跑。
`Inject a failure at` 下拉框是刻意留的:演示"失败会怎样"不用断网、不用改代码。
黄色 CTA 一屏只有一个(UI-STYLE §4),就是 Run demo job。

## StyleGuidePage:为什么色值是读回来的

它显示的 hex 用 `getComputedStyle(document.documentElement).getPropertyValue('--brand-navy')`
读回真值,而不是在页面里再抄一份色表 —— 否则这一页自己就会变成第二处色值出处,
"hex 只出现在 token 定义处"的纪律就破了。着色一律 `style={{background: 'var(--x)'}}`。

## 文案纪律

界面文案全英文(D5),locale 固定 `en-AU`(`lib/format.ts`)。
文案说清"这个模块为什么存在"(例:三类知识按容错率分层),演示时不用另外解释。
