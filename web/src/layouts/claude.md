# web/src/layouts/

**职责**:三栏工作台骨架。

| 文件 | 说明 |
| --- | --- |
| `AppLayout.tsx` | 浅色侧栏 224px + 顶栏 64px + 白底内容区 + 右侧面板 320px(可折叠) |
| `rightPanel.tsx` | 右侧面板的 context 与 `useRightPanel(title, node, deps)`;**单独一个文件是为了断环**(域页面要用它,而 AppLayout 要遍历 DOMAINS) |

侧栏入口是 `NAV_MAIN`/`NAV_FOOT` 两张表 + **两个可展开分组**:
"How It Works"(子项遍历 `pages/how-it-works` 的 `HOW_IT_WORKS_NAV`:总页 / 三层)与
"Knowledge Ingestion"(子项遍历 `domains/index.ts` 的 DOMAINS,识别色圆点);
顶栏标题是 `TITLES` 表(域标题也是生成的)。
两个分组的子项清单都在别处,本文件不硬编码任何一页。详见 `architect.md`。
