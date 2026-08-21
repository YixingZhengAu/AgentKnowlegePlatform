# web/src/components/staging/

**职责**:各类知识的审核渲染器 —— `<StagingReview>` 与"这条东西长什么样"之间的唯一接口。

| 文件 | 说明 |
| --- | --- |
| `types.ts` | 渲染器契约:`ItemCardProps` / `ItemEditorProps` / `OriginPanelProps` + payload 取值工具 |
| `registry.ts` | `item_type → 渲染器` 注册表;没登记的类型落到 JSON 兜底 |
| `QaRenderers.tsx` | 精准 QA(`qa_pair`):列表卡片 + 编辑器 + 溯源面板 |
| `JsonRenderers.tsx` | 兜底:直接看/改 payload 的 JSON(新类型还没写渲染器时也能审) |

**加一类知识 = `registry.ts` 加一行 + 写一对渲染器**,审核台本身不动。

详见 `architect.md`。
