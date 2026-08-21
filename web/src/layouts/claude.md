# web/src/layouts/

**职责**:三栏工作台骨架。

| 文件 | 说明 |
| --- | --- |
| `AppLayout.tsx` | navy 侧栏 220px + 白顶栏 56px + 内容区 + 右侧面板 360px(可折叠);
导出 `useRightPanel(title, node)` 供页面往右栏塞内容 |

侧栏入口与顶栏标题分别是文件里的 `NAV` / `TITLES` 两张表。详见 `architect.md`。
