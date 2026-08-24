# web/src/pages/how-it-works/

**职责**:面试投屏用的**项目说明页**(讲设计思想,不是使用手册)。零后端依赖。
计划见 `documents/HOW-IT-WORKS-PLAN.md`。

| 文件 | 说明 |
| --- | --- |
| `content.ts` | **文案唯一出处**:主张 / 七条痛点 / 治理骨架 / 回答链路 / 两条泳道 / 三层对比 / 取舍 / 三个子页的六段 |
| `figures.tsx` | 四张图(倒漏斗、治理骨架、回答链路、泳道),纯填充块,无图表库 |
| `Section.tsx` | 排版元件;**UI-STYLE 演示页字阶的唯一落地处**(24px 以上 sans 只许出现在这里) |
| `OverviewPage.tsx` | 总页:主张块 + 三层卡片常驻,六个论点折叠区(默认收起当目录) |
| `LayerPage.tsx` | 子页 `/how-it-works/:layer`:主角句 + 示例 chips + 四张关键词卡 + may/may not 两列 |

**纪律**:组件里不写死句子;不 import 任何 `domains/*`(识别色用 `bg-kb-*` 工具类)。

详见 `architect.md`。
