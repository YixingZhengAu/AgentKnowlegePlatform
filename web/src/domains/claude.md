# web/src/domains/

**职责**:各类知识的前端隔离边界 —— 一域一文件夹,并行开发互不打架(结构调整,见 S0-PLAN §5)。
前三个域是落地的知识类型;`workflow` 是第四种(编排),**只有静态设计预览、没有后端**。

| 路径 | 说明 |
| --- | --- |
| `index.ts` | **唯一共享落笔点**:DOMAINS 数组;加一个域 = 这里加一行 |
| `types.ts` | `DomainModule` 描述符类型(路由/导航/标题/识别色/页面/渲染器) |
| `exact-qa/` | 精准 QA 域,见 `exact-qa/claude.md` |
| `document/` | 文档 RAG 域(上传 PDF → 五步摄取 → 切片审核台 `chunk` 渲染器 + 合并相邻),见 `document/claude.md` |
| `text2sql/` | 智能问数域(D1 数据源 / D2 Schema 治理 / D3 意图台账 / D4 意图详情 / D5 chat 展示,全部已自测),见 `text2sql/claude.md` |
| `workflow/` | **编排域(第四种知识,已设计未落地)**:一页静态画布预览,零后端零交互;设计说明在 `/how-it-works#workflows`,见 `workflow/claude.md` |

**纪律**:域文件夹之间禁止互相 import;只向上依赖 shared 层(`src/{api,components,layouts,lib}`,对域开发者只读)。

详见 `architect.md`。
