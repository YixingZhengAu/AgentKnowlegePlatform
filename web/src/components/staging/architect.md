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

## 动作层(types.ts 的 ReviewActions,Step 7a 加出来的)

审核台负责**流程**,"通过/驳回到底做了什么"归各域:

```ts
ReviewActions = {
  approveLabel, requireRejectNote?, defaultStatusFilter?, publish?, bulk?, bulkReject?,
  approve(item, payloadOrNull), reject(item, note), bulkApprove?(items) -> 成功条数,
}
```

不传就是 S0 默认语义(`PATCH /api/staging/{id}` 标 approved,最后 `POST /api/jobs/{id}/publish`
批量发布)。S1 换成**采纳即发布**:approve 打 `/api/exact-qa/candidates/{id}/accept`
(一个事务写正式表 + 建向量),`publish: false` 让批量发布按钮消失、`requireRejectNote` 让
驳回必须填理由。不抽这一层就只有两条烂路:泛型组件里 if 域名,或者各域复制一份审核台。

**批量(Step 8 补的)**:S0 的批量是一次 `POST /api/staging/bulk` 改状态;S1 的采纳要写正式表
+ 建向量,没有批量端点,所以本域给 `bulkApprove` —— 审核台优先用它,**串行**逐条打接口,
返回真正成功的条数,少了就按 `3 items approved (2 failed)` 如实报。`bulkReject: false`
关掉批量驳回:理由必填,批量填一个理由等于没理由。

## 注册表(registry.ts)

```
RENDERERS = 各域 module.ts 的 renderers 合并(遍历 src/domains/index.ts 的 DOMAINS)
没登记的  → FALLBACK_RENDERERS(JSON 卡片 + JSON 编辑器)
```

本文件不认识任何具体域。`renderersFor(itemType)` 是唯一查询入口。
当前已登记:`qa_pair`(精准 QA 域,含 `actions`)。其余 item_type 走 JSON 兜底 ——
这正是兜底存在的意义:后端任务写出 staging 条目、渲染器还没动手时,审核台已经能用
(看 JSON、改 JSON、通过驳回),不必等前端补齐。

## JSON 编辑器的一个细节

- **只在解析成功时上报**:改坏的 JSON 不该被当成一次编辑
  (否则一边打字一边就把 payload 写成半截了)

## 我要改 X 去哪

| 改什么 | 去哪 |
| --- | --- |
| 加一类知识的审核界面 | `src/domains/<域>/` 写一对渲染器 + 该域 `module.ts` 的 `renderers` 登记 |
| 列表里一行显示什么 | 对应域渲染器的 `*ItemCard` |
| 原文对照面板 | 对应域渲染器的 `*OriginPanel`(S2 文档 RAG 的重点) |
| 采纳/驳回的动作语义 | 对应域的 `actions.ts`(`ReviewActions`) |
| 渲染器与动作的契约本身 | `types.ts`(公共契约变更,单独提,不夹在域开发里) |
