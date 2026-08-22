# web/src/domains/exact-qa/ · architect

## 页面与路由

```
/ingest/exact-qa                                    DocumentsPage(上传 + 文档列表 + 已发布库)
/ingest/exact-qa/documents/:documentId/proofread    ProofreadPage(第一道人工关)
/jobs/:jobId/review                                 共享审核台 + 本域渲染器与动作(第二道人工关)
```

共享路由表只给每个域一个 `/ingest/<域>/*` 空间(`src/App.tsx`),域内二级页在
`IngestPage.tsx` 的 `<Routes>` 里摆 —— **本域加页面不需要碰任何共享文件**。

## 上传者旅程与页面的对应

| 旅程步骤 | 落在哪 | 出口动作 |
| --- | --- | --- |
| ① 上传 PDF | `DocumentsPage` 的上传卡 | `POST /api/exact-qa/documents`(建 source+document+parse Job) |
| ② 等解析 | 文档列表那一行(stage 自己变) | 有文档在跑才轮询,到终态停 |
| ③ 校对解析文本 | `ProofreadPage` | 「Confirm & extract Q&A」→ 派发 qa_extract |
| ④ 采纳候选 | 共享审核台 + `renderers`/`actions` | Accept & publish / Reject(理由必填) |
| ⑤ 看结果 | `ItemsPanel` | Disable(下线,不是删除) |
| (清场) | 文档列表那一行的垃圾桶 | `DELETE /api/exact-qa/documents/{id}`,**两步确认**;有已发布问答的后端 409 |

## 审核台是怎么复用的(Step 7a)

泛型审核台 `components/StagingReview` 负责流程(筛选/排序/键盘流/选中推导),
**动作层由本域提供**(`components/staging/types.ts` 的 `ReviewActions`):

```
qaPairActions = {
  approveLabel: 'Accept & publish',
  requireRejectNote: true,        // 不采纳的理由是下一轮调 prompt 的素材
  defaultStatusFilter: 'pending', // 审核台在本域是工作队列,裁决完就该消失
  publish: false,                 // 采纳即发布 —— 没有批量发布这一步
  bulk: true, bulkReject: false,   // 批量采纳有(Step 8 补);批量驳回没有 —— 理由必填
  approve:     (item, payload) => [PATCH /api/staging/{id} 若有改动] → POST /candidates/{id}/accept,
  bulkApprove: (items)        => 串行逐条 accept,返回成功条数,
  reject:      (item, note)   => POST /candidates/{id}/reject,
}
```

顺序很重要:**先落盘改动再采纳**,反了就会把改动前的内容发布出去。
批量采纳刻意**串行**:每条都要 embedding + 写库,并发只是把限流和"一半成功"的概率放大;
失败的跳过,审核台按 `3 items approved (2 failed)` 如实报数(不假装全成了)。

## 校对页的三个实现要点

1. **左 PDF 用浏览器原生阅读器**(`iframe src=/api/files/documents/{id}/pdf#page=N`)——
   不引 pdf.js:S1 需要的只是"翻到第 N 页对着看"。
   代价:**bbox 高亮做不了**(要在 PDF 上叠画布),所以引用定位落在"在编辑器里选中那句原文"。
2. **`<!-- page: N -->` 标记不能删**:抽取靠它给候选标页码;编辑器里它是普通文本,
   所以有一道"标记少了 N 个"的提示(不拦保存,只提醒)。
3. **自动定位引用挂在 ref 回调上,不是 effect**:文档与文本是两个请求,
   先回来的那个会让组件还停在骨架态 —— effect 触发时 textarea 还没挂上(ref 是 null),
   等它挂上时依赖又没变。Step 7b 的浏览器自测抓到过这个"手点能跳、自动跳不动"。

## 状态从哪来

`DocumentOut.stage` 是**后端推导**的(`server/app/api/exact_qa.py::_stage`):文档表只存解析态,
"待校对 / 抽取中 / 待采纳 / 完成"由关联 Job 推出来。前端只做 stage → 文案/色/动作的映射
(`schema.ts` 的 `STAGE_LABEL` / `stageTone` / `DocumentsPage.RowAction`),**不自己拼状态**。

## 我要改 X 去哪

| 改什么 | 去哪 |
| --- | --- |
| 候选列表一行显示什么 | `renderers.tsx` 的 `QaItemCard` |
| 候选可编辑哪些字段 | `renderers.tsx` 的 `QaItemEditor` |
| 采纳/不采纳打哪个接口 | `actions.ts` |
| 文档列表的动作按钮 | `DocumentsPage.tsx` 的 `RowAction` |
| 删文档的确认与提示 | `DocumentsPage.tsx` 的 `remove` + `confirmId` |
| 批量采纳怎么打接口 | `actions.ts` 的 `bulkApprove` |
| stage 的文案与颜色 | `schema.ts` 的 `STAGE_LABEL` / `stageTone` |
| markdown 渲染样式 | `MarkdownView.tsx` 的 `MD_COMPONENTS` |
