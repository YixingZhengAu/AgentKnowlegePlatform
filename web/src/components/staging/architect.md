# staging/ 内部结构

## 渲染器契约(types.ts)

```ts
ItemCardProps   = { item: StagingItem }                       // 列表里一眼看懂
ItemEditorProps = { payload, onChange(patch), disabled? }     // 怎么改
OriginPanelProps= { item: StagingItem }                       // 原文对照(可选)
```

`payload` 是 jsonb(结构见 DB-DESIGN §8),所以类型只能是 `Record<string, unknown>` ——
**泛型审核台的全部意义就是不认识 payload 里有什么**。`str()` / `strList()` 两个小工具
负责"从 jsonb 里安全取值":后端改了字段名,这里拿到空字符串而不是 crash。

`onChange` 只回传**改动的顶层键**,与后端 `PATCH` 的浅合并语义对齐
(`core/staging.py::merge_payload`),所以编辑器不必持有整份 payload 的副本。

## 注册表(registry.ts)

```
qa_pair → { card: QaItemCard, editor: QaItemEditor, origin: QaOriginPanel }
其它     → FALLBACK_RENDERERS(JSON 卡片 + JSON 编辑器)
```

`renderersFor(itemType)` 是唯一查询入口。兜底渲染器不是摆设:S2 的切片任务写出来、
渲染器还没动手时,审核台**已经能用**(看 JSON、改 JSON、通过驳回),
不必等前端补齐才能验证后端。

## QA 渲染器的两个细节

- **相似问按行编辑**:`textarea` 的每一行是一个相似问,空行被过滤 ——
  审核时按回车换行是常态,不该留下空条目
- **JSON 编辑器只在解析成功时上报**:改坏的 JSON 不该被当成一次编辑
  (否则一边打字一边就把 payload 写成半截了)

## 我要改 X 去哪

| 改什么 | 去哪 |
| --- | --- |
| 加一类知识的审核界面 | `registry.ts` 加一行 + 新写一对渲染器文件 |
| QA 编辑器加字段 | `QaRenderers.tsx` 的 `QaItemEditor`(payload 键名对齐 DB-DESIGN §8) |
| 列表里一行显示什么 | 对应渲染器的 `*ItemCard` |
| 原文对照面板 | 对应渲染器的 `*OriginPanel`(S2 文档 RAG 的重点) |
