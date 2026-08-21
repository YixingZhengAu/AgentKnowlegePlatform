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

## StyleGuidePage:为什么色值是读回来的

它显示的 hex 用 `getComputedStyle(document.documentElement).getPropertyValue('--brand-navy')`
读回真值,而不是在页面里再抄一份色表 —— 否则这一页自己就会变成第二处色值出处,
"hex 只出现在 token 定义处"的纪律就破了。着色一律 `style={{background: 'var(--x)'}}`。

## 文案纪律

界面文案全英文(D5),locale 固定 `en-AU`(`lib/format.ts`)。
文案说清"这个模块为什么存在"(例:三类知识按容错率分层),演示时不用另外解释。
