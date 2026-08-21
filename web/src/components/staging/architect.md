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
RENDERERS = 各域 module.ts 的 renderers 合并(遍历 src/domains/index.ts 的 DOMAINS)
没登记的  → FALLBACK_RENDERERS(JSON 卡片 + JSON 编辑器)
```

本文件不认识任何具体域。`renderersFor(itemType)` 是唯一查询入口。
当前**没有任何域登记渲染器**(旧 QA 渲染器随 RESTRUCTURE-PLAN Stage 2 删除),
所以所有 item_type 都走 JSON 兜底 —— 这正是兜底存在的意义:后端任务写出 staging 条目、
渲染器还没动手时,审核台已经能用(看 JSON、改 JSON、通过驳回),不必等前端补齐。

## JSON 编辑器的一个细节

- **只在解析成功时上报**:改坏的 JSON 不该被当成一次编辑
  (否则一边打字一边就把 payload 写成半截了)

## 我要改 X 去哪

| 改什么 | 去哪 |
| --- | --- |
| 加一类知识的审核界面 | `src/domains/<域>/` 写一对渲染器 + 该域 `module.ts` 的 `renderers` 登记 |
| 列表里一行显示什么 | 对应域渲染器的 `*ItemCard` |
| 原文对照面板 | 对应域渲染器的 `*OriginPanel`(S2 文档 RAG 的重点) |
| 渲染器契约本身 | `types.ts`(公共契约变更,单独提,不夹在域开发里) |
