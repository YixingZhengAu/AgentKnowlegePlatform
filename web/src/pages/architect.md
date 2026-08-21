# web/src/pages/architect.md

## 页面的统一写法

```tsx
const state = useApi<AgentList>('/api/agents')    // 三态在 hook 里
<Card><CardHeader>…</CardHeader>
  <DataState state={state} isEmpty={…} emptyIcon={…} emptyTitle="…">
    {(data) => <Table>…</Table>}
  </DataState>
</Card>
```

卡片标题**不要跟顶栏标题重复**(顶栏已经写了页面名,卡片写更具体的一层)。

## ChatPage:三块拼起来

```
[会话列表 240px] [消息流 + 输入框] │ 右侧面板挂 <TracePanel>(AppLayout 的插槽)
```

- **"新对话"没有对应的接口**:后端不传 `conversation_id` 就等于新开一轮,
  所以点 New chat 只是清空本地状态 —— 少一次往返,也不留"建了但没发消息"的空会话。
- 删除是软删(`DELETE /api/conversations/{id}` → status=archived),消息与 trace 都留着。
- 右侧面板默认盯最后一条助手消息;点某条气泡就切到那条(历史消息会去查完整 trace)。
- 流结束后再刷一次会话列表:标题与 `last_message_at` 是后端在这一轮里写的。

## ReviewPage:一页七行

```tsx
const renderers = renderersFor(probe.data?.items[0]?.item_type)
<StagingReview jobId={jobId} jobStatus={job.data.status}
  itemRenderer={renderers.card} editorRenderer={renderers.editor}
  originPanel={renderers.origin} onPublished={job.reload} />
```

页面自己几乎不做事:查一下这批待审内容是什么类型(只取一条:渲染器按类型选,不按条目选),
从注册表取渲染器,交给审核台。右侧面板挂 `<JobProgress>` —— 审核时还能看见"这批是怎么来的"。
S1/S2/S3 的审核入口都会长成这七行。

入口:旧任务列表页已删(结构调整,见 S0-PLAN §5),当前用直链 `/jobs/{id}/review`
(demo 任务用 curl/脚本提交);正式入口由各域开发者在 `src/domains/<域>/` 里做。
`<JobProgress>` 跑完后的 Review 按钮仍在(框架件)。

## StyleGuidePage:为什么色值是读回来的

它显示的 hex 用 `getComputedStyle(document.documentElement).getPropertyValue('--brand-navy')`
读回真值,而不是在页面里再抄一份色表 —— 否则这一页自己就会变成第二处色值出处,
"hex 只出现在 token 定义处"的纪律就破了。着色一律 `style={{background: 'var(--x)'}}`。

## 文案纪律

界面文案全英文(D5),locale 固定 `en-AU`(`lib/format.ts`)。
文案说清"这个模块为什么存在"(例:三类知识按容错率分层),演示时不用另外解释。
