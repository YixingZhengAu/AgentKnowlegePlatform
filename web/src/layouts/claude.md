# web/src/layouts/

**职责**:三栏工作台骨架。

| 文件 | 说明 |
| --- | --- |
| `AppLayout.tsx` | navy 侧栏 220px + 白顶栏 56px + 内容区 + 右侧面板 360px(可折叠) |
| `rightPanel.tsx` | 右侧面板的 context 与 `useRightPanel(title, node, deps)`;**单独一个文件是为了断环**(域页面要用它,而 AppLayout 要遍历 DOMAINS) |

侧栏入口是 `NAV_MAIN`/`NAV_FOOT` 两张表 + "Knowledge Ingestion" 可展开分组(子项遍历
`domains/index.ts` 的 DOMAINS 生成,识别色圆点);顶栏标题是 `TITLES` 表(域标题也是生成的)。
本文件不出现任何具体域的硬编码。详见 `architect.md`。
