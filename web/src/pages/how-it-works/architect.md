# how-it-works · 结构说明

## 这页是什么

一副长在系统里的**幻灯片**:屏幕共享时讲哪点开哪,把「为什么这么设计」讲完。
不放技术细节(不出现表名、字段名、接口路径、阈值),不做深链,不动后端。
**体裁是关键词,不是文章**(2026-08-24 需求方定):面试官不会逐句读,全篇只保留
两类完整句 —— 每层一句主角句、每屏一句强调句,其余一律关键词/短语。

## 内容骨架(总页)

结构 = 两个常驻块 + 六个折叠区(2026-08-24 需求方定,替代八屏长滚):

| 块 | 数据来源(`content.ts`) | 图 |
| --- | --- | --- |
| 常驻:The claim | `CLAIM` + `FUNNEL` | `FunnelFigure` |
| 常驻:The three layers(进子页) | `LAYERS` + `LAYER_CARDS_TITLE` | 三张卡片 |
| 折叠:Why generic RAG isn’t enough | `PAIN_POINTS`(症状 → 回答) | — |
| 折叠:Three layers, one gate | `GATE` + `LAYERS` | `GateFigure` |
| 折叠:What happens when someone asks | `ANSWER_FLOW` | `AnswerFlowFigure` |
| 折叠:Who uses it, and how | `ROLES` | `RolesFigure` |
| 折叠:The three layers side by side | `COMPARISON` | 表(全页唯一) |
| 折叠:What we deliberately don’t do | `TRADEOFFS` | — |

折叠区由 `Section.tsx` 的 `CollapsibleScreen` 实现:默认收起,折叠态一行 =
24px 标题 + 13px 关键词摘要(`*.summary`),当目录用,讲哪点开哪。

三条推论(`CLAIM.corollaries`)是全篇地基:前置而非临场 / 业务团队是知识的所有者 /
RAG 是兜底。检索顺序 **精准问答 → Text-to-SQL → 文档 → 说没有依据** 与后端 `core/chat.py`
的 stage 顺序一致。命名纪律:该层全站叫 **Text-to-SQL**(与侧栏一致),不再自创别名。

## 子页

`LAYER_DETAILS[slug]`,三页同一结构:主角句 + 示例 chips → 四张关键词卡
(What it’s for / Why it can’t be improvised / Settled up front / Where the business steps in,
业务介入那张黄色识别条高亮)→ **may / may not 两列**(绿底/红底,全站状态色)→ Deliberately doesn’t。

文档 RAG 那页**照常写、不标未实现**(需求方 2026-08-24 决定),因此只讲设计取向,不描述界面。

## 排版

`Section.tsx` 收敛 UI-STYLE §2「演示页字阶(作用域仅 /how-it-works)」:主张 34 / 屏标题 30 /
段标题 20 / 正文 17·1.65 / 强调 19 / meta 13。内容最大宽 860px,屏间距 88px,屏内 28px,
右侧面板不挂载。行内强调只支持 `**...**`,由 `Section.tsx` 的 `<Emphasized>` 解析。

`figures.tsx` 用填充块而非 SVG:图里的说明句较长,SVG `<text>` 不换行、窄屏必溢出;
填充块既合「白底 + 填充块」的基调,也天然自适应。倒漏斗保留几何语义(块宽自上而下递增 =
模型自由度递增)。

## 我要改 X 去哪

| 要改 | 去哪 |
| --- | --- |
| 任何一句文案 | `content.ts`(唯一出处) |
| 图的画法 | `figures.tsx` |
| 字号 / 行长 / 屏间距 | `Section.tsx` + `OverviewPage.tsx` 的容器类 |
| 加一屏 | `content.ts` 加数据 + `OverviewPage.tsx` 加一个 `<Screen>` |
