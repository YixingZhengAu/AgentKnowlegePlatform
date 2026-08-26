# web/src/domains/ · architect

## 设计:manifest 模式

每个域导出一个 `DomainModule` 描述符(`types.ts` 定义),`index.ts` 把三个描述符收进
`DOMAINS` 数组。所有共享触点改为遍历 `DOMAINS` 生成,不再手写:

| 共享文件 | 从描述符取什么 |
| --- | --- |
| `src/App.tsx` | `path` + `IngestPage` → 生成 `/ingest/*` 路由 |
| `src/layouts/AppLayout.tsx` | `label` + `path` + `toneClass` → "Knowledge Ingestion" 二级导航;`label` → 顶栏标题(`<label> Ingestion`) |
| `src/components/staging/registry.ts` | `renderers`(item_type → 渲染器)→ 合并进审核台注册表 |
| `src/components/Citations.tsx` | `citations`(citation_type → 引用渲染器)→ chat 气泡里那条引用;没登记走通用引用条(S3 加出来的一层:问数命中要画结果表格 + 最终 SQL) |

于是"加一个域"对共享代码的影响收敛为 `index.ts` 的一行 import + 一行数组项 ——
这是并行开发时唯一可能冲突的文件,冲突形态是相邻两行,git 自动合并即可。

用显式数组而不是 import 副作用注册:tree-shaking 下副作用不可靠,且显式列表可读。

## 域文件夹内的约定

- `module.ts`:描述符,域对外的全部信息
- `IngestPage.tsx`:域内**路由壳**(三个域现在都是真页面)。
  域内二级页在这里摆 `<Routes>`,加页面不碰共享文件;
  本域的一切新代码(组件/hooks/渲染器)都落在本文件夹
- 识别色:UI-STYLE §2 —— QA=黄 / 文档=蓝 / 问数=紫;组件里只用 `bg-kb-*` 工具类,
  hex 只存在于 `src/index.css` 品牌层
- 渲染器契约见 `src/components/staging/types.ts`;没注册的 item_type 走 JSON 兜底,
  所以渲染器可以最后写。引用渲染器契约是 `src/components/Citations.tsx` 导出的
  `CitationRenderer`,**登记表在渲染时才查** —— 在模块顶层算会在 DOMAINS 初始化期间
  被求值,拿到 undefined(与"域里不许 import AppLayout"是同一个环)

## 依赖方向(禁止逆行/横行)

```
domains/exact-qa ─┐
domains/document ─┼─→ src/{api,components,layouts,lib}(shared 层,域开发者只读)
domains/text2sql ─┘        ↑
        └── 兄弟域之间禁止 import ──┘(不存在的箭头)
```

shared 层要改 = 公共契约变更,单独提出来评审,不夹在域开发里。
