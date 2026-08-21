# web/src/

**职责**:前端应用代码。入口 `main.tsx` → `App.tsx`(路由)→ `layouts/AppLayout`(三栏)。

| 路径 | 说明 |
| --- | --- |
| `main.tsx` | 挂载 React + BrowserRouter,引入 `index.css` |
| `App.tsx` | 路由表(`/chat` `/kbs` `/agents/:id` `/settings` + 隐藏 `/styleguide`)+ `<Toaster/>` |
| `index.css` | **全站唯一色源**:品牌原色 → 语义变量 → Tailwind `@theme`(三层,见 `../architect.md`) |
| `api/` | 后端交互层,见 `api/claude.md` |
| `components/` | 通用组件,见 `components/claude.md` |
| `layouts/` | 三栏骨架,见 `layouts/claude.md` |
| `pages/` | 页面,见 `pages/claude.md` |
| `lib/` | 无 React 依赖的工具,见 `lib/claude.md` |

详见 `architect.md`。
