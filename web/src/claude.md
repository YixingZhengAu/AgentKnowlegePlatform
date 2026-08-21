# web/src/

**职责**:前端应用代码。入口 `main.tsx` → `App.tsx`(路由)→ `layouts/AppLayout`(三栏)。

| 路径 | 说明 |
| --- | --- |
| `main.tsx` | 挂载 React + BrowserRouter,引入 `index.css` |
| `App.tsx` | 路由表(`/chat` `/agents/:id` `/ingest/*`(遍历 DOMAINS 生成)`/jobs/:id/review` `/settings` + 隐藏 `/styleguide`)+ `<Toaster/>` |
| `index.css` | **全站唯一色源**:品牌原色 → 语义变量 → Tailwind `@theme`(三层,见 `../architect.md`) |
| `api/` | 后端交互层,见 `api/claude.md` |
| `components/` | 通用组件,见 `components/claude.md` |
| `domains/` | **三类知识的隔离边界**(一域一文件夹,并行开发),见 `domains/claude.md` |
| `layouts/` | 三栏骨架,见 `layouts/claude.md` |
| `pages/` | 跨域公共页面,见 `pages/claude.md` |
| `lib/` | 无 React 依赖的工具,见 `lib/claude.md` |

**分层纪律**:`api/components/layouts/lib` 是 shared 层,域开发者只读;
域代码只落在 `domains/<域>/`,禁止 import 兄弟域(RESTRUCTURE-PLAN)。

详见 `architect.md`。
