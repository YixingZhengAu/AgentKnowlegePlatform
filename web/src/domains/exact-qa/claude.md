# web/src/domains/exact-qa/

**职责**:精准 QA(exact_qa)域前端 —— 上传 / 校对 / 采纳 的一切代码都落在这里。

| 文件 | 说明 |
| --- | --- |
| `module.ts` | 域描述符(路由 `/ingest/exact-qa`、识别色黄、`qa_pair` 渲染器 + 动作登记) |
| `IngestPage.tsx` | 域内路由壳(`/ingest/exact-qa/*` 的二级页在这里摆) |
| `DocumentsPage.tsx` | 首页:上传 PDF + 文档列表(stage / 漏斗 / 一行一个动作 + 删除)+ 已发布问答库 |
| `ProofreadPage.tsx` | 校对页:左 PDF 原件、右 markdown 编辑/预览,出口是「Confirm & extract」 |
| `ItemsPanel.tsx` | 已发布问答库:`index_faces`(在不在索引里)+ 下线 |
| `renderers.tsx` | `qa_pair` 审核渲染器(卡片 / 编辑器 / 原文对照) |
| `actions.ts` | 审核动作层:**采纳即发布**(accept / 批量 accept / reject,理由必填) |
| `MarkdownView.tsx` | 解析文本渲染(允许原始 HTML:MinerU 的表格与上下标) |
| `pagedMd.ts` | 页标记纯函数(切页 / 页锚点),与渲染分开 |
| `schema.ts` | 生成类型的短名 + stage 文案/色 + jsonb 读取工具(**不手写 API 类型**) |

详见 `architect.md`;跨域约定见 `../claude.md`。
