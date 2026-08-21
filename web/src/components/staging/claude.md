# web/src/components/staging/

**职责**:审核渲染器的契约与汇总 —— `<StagingReview>` 与"这条东西长什么样"之间的唯一接口。

| 文件 | 说明 |
| --- | --- |
| `types.ts` | 渲染器契约:`ItemCardProps` / `ItemEditorProps` / `OriginPanelProps` + payload 取值工具 |
| `registry.ts` | 汇总各域 manifest 登记的 `item_type → 渲染器`;没登记的类型落到 JSON 兜底 |
| `JsonRenderers.tsx` | 兜底:直接看/改 payload 的 JSON(渲染器还没写时任何类型都能审) |

**加一类知识的审核界面 = 在 `src/domains/<域>/` 写一对渲染器 + 在该域 `module.ts` 的
`renderers` 登记**;本目录与审核台本身不动(结构调整,见 S0-PLAN §5)。

详见 `architect.md`。
