# web/src/pages/how-it-works/

**职责**:面试投屏用的**项目说明页**(讲设计思想与架构,不是使用手册)。零后端依赖。
计划见 `documents/HOW-IT-WORKS-PLAN.md`(v2 在 §10,v2.1 架构段并回总页在 §11)。

| 文件 | 说明 |
| --- | --- |
| `content.ts` | **文案唯一出处**:主张 / 四条立场 / 痛点 / 治理骨架 / 三层对比 / 取舍;架构段六小节(六层技术架构 / 外壳内核 / 一次请求 / 闭环 / 四层评估 / 自主性边界);页脚署名 `AUTHORS`;三个子页(含每层两条流程);**侧栏子项清单 `HOW_IT_WORKS_NAV`** |
| `figures.tsx` | 全部图形(倒漏斗、治理骨架、技术架构、外壳内核、请求链路、角色闭环、评估、自主性边界、子页流程),纯填充块,无图表库 |
| `Section.tsx` | 排版元件;**UI-STYLE 演示页字阶的唯一落地处**(24px 以上 sans 只许出现在这里) |
| `OverviewPage.tsx` | 总页 `/how-it-works`(**一页讲完**):主张 → 四条立场 → 架构段(六小节 + 锚点条)→ 三层卡片 → 四个折叠区 → 署名 |
| `LayerPage.tsx` | 子页 `/how-it-works/:layer`:主角句 + 示例 → 治理/回答两条流程 → 四张关键词卡 → may/may not |
| `index.ts` | 对外只导出两个页面组件 + `HOW_IT_WORKS_NAV`(给 AppLayout 摆侧栏) |

**纪律**:组件里不写死句子;不 import 任何 `domains/*`(识别色用 `bg-kb-*` 工具类)。

详见 `architect.md`。
