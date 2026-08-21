# web/src/domains/

**职责**:三类知识的前端隔离边界 —— 一域一文件夹,并行开发互不打架(RESTRUCTURE-PLAN)。

| 路径 | 说明 |
| --- | --- |
| `index.ts` | **唯一共享落笔点**:DOMAINS 数组;加一个域 = 这里加一行 |
| `types.ts` | `DomainModule` 描述符类型(路由/导航/标题/识别色/页面/渲染器) |
| `exact-qa/` | 精准 QA 域,见 `exact-qa/claude.md` |
| `document/` | 文档 RAG 域,见 `document/claude.md` |
| `text2sql/` | 智能问数域,见 `text2sql/claude.md` |

**纪律**:域文件夹之间禁止互相 import;只向上依赖 shared 层(`src/{api,components,layouts,lib}`,对域开发者只读)。

详见 `architect.md`。
