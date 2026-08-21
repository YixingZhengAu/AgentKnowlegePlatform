# web/src/components/ui/architect.md

## 与上游 shadcn/ui 的差异(故意的)

1. **不装 Radix 也不引 `@radix-ui/react-slot`**:S0 用到的都是原生元素,
   `asChild` 这类能力等真需要(Dialog / Popover)时再按需 `npx shadcn add`
2. 颜色一律走语义 token(`bg-primary` / `text-accent-foreground`),
   删掉了 shadcn 默认的 slate 色阶 —— 保证"改 UI-STYLE 就能改全站"
3. 圆角写 `rounded-[var(--radius)]` / `rounded-[var(--radius-card)]`,不用 Tailwind 的数字圆角:
   6px / 12px 两档是规范定的,不允许在组件里随手改成 `rounded-lg`

## variant 的边界

`accent`(黄底 navy 字)对应"发布"级动作,**一屏最多一个**(UI-STYLE §4)。
新增 variant 前先确认 UI-STYLE §3 的按钮表里有没有,没有就先改文档。
