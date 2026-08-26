# web/src/domains/document/ · architect

## 页面与路由

```
/ingest/document        DocumentsPage(上传 + 文档列表)
/jobs/:jobId/review     共享审核台 + 本域渲染器与动作(唯一一道人工关)
```

共享路由表只给每个域一个 `/ingest/<域>/*` 空间(`src/App.tsx`),域内二级页在
`IngestPage.tsx` 的 `<Routes>` 里摆 —— **本域加页面不需要碰任何共享文件**。
本域目前只有 index 一页:文档 RAG 没有"先校对解析文本"那一关(那是 S1 的做法),
审的直接就是切片本身。

## 上传者旅程与页面的对应

| 旅程步骤   | 落在哪                             | 出口动作                                                |
| ---------- | ---------------------------------- | ------------------------------------------------------- |
| ① 上传 PDF | `DocumentsPage` 的上传卡           | `POST /api/document/documents`(multipart 字段名 `file`) |
| ② 等切片   | 文档列表那一行(stage 自己变)       | 有文档在跑才轮询,到终态停                               |
| ③ 审切片   | 共享审核台 + `renderers`/`actions` | Keep chunk / Reject / Merge with next                   |
| ④ 发布     | 审核台底部的批量发布               | 整批 approved 一次性进索引                              |
| (清场)     | 文档列表那一行的垃圾桶             | `DELETE /api/document/documents/{id}`,**两步确认**      |

## 数据流(一张图)

```
DocumentsPage ──POST /api/document/documents──▶ doc_ingest Job(parse→clean→chunk→describe→stage)
      ▲                                                        │
      └── GET /api/document/documents(有 active 才轮询)◀───────┘ 写 staging_items(item_type=chunk)
                                                                 │
/jobs/:jobId/review ── GET /api/staging?job_id=… ────────────────┘
      │  item_type=chunk → registry 查到本域三件套
      ├─ ChunkItemCard   ← StagingItem   ⇒ 一行看懂:#seq / 标题路径 / token / 图表种类
      ├─ ChunkItemEditor ← 只有 payload   ⇒ 一个正文输入框(只有正文会被检索)
      └─ ChunkOriginPanel← StagingItem   ⇒ PDF 翻到 page+1 + 图表对照 + Merge with next
```

`stage` 是后端推导的五态(`pending / ingesting / review / published / failed`),
前端只做 stage → 文案/色/动作的映射(`schema.ts` 的 `STAGE_LABEL` / `stageTone` /
`DocumentsPage.RowAction`),**不自己拼状态**。

## payload / origin_ref 的形状(jsonb,openapi 里只有 `dict`)

```
payload    = {seq, content, heading_path[], token_count, page_idx, bbox, figures[]}
figures[i] = {kind: image|chart|table, img: "images/<sha>.jpg", description, truncated,
              source_caption[], source_footnote[], page_idx, bbox}
origin_ref = {document_id, page, bbox}      ← 注意不是 S1 那个 OriginRef(quote/page_idx)
```

读它们一律经过 `schema.ts` 的 `readChunkPayload` / `readOriginRef`,不假设类型。
静态产物地址在 `files.ts`:图片 `/api/files/parses/{document_id}/images/<sha>.jpg`,
原件 `/api/files/documents/{document_id}/pdf#page=N&view=FitH`。

## 「Merge with next」与图表为什么在 origin 槽

审核台的布局是共享组件的(`components/StagingReview`),域只能往三个槽里塞东西:
卡片 / 编辑器 / 原文对照。这个动作既不是"通过"也不是"驳回",挂不进底部动作条。

🩸 **它不能放在编辑器里**:`ItemEditorProps` 只有 `{payload, onChange, disabled}`,
**拿不到 `StagingItem`** —— 而合并要 `item.id`、图片地址要 `origin_ref.document_id`,
两者 payload 里都没有。`OriginPanelProps` 有完整的 `item`,而且它就渲染在编辑区正下方、
同一个右栏里,人看起来是连着的一块。

曾经写过另一版:卡片渲染时把 `seq → (item id, document id)` 记进一个模块级 Map,
编辑器再按 seq 查回来。**已删掉** —— 那是渲染期副作用,依赖"左侧列表先于右侧渲染"这个
共享组件的内部实现细节,列表一旦虚拟化或换成并发渲染就会静默失效。
既然 origin 槽本来就拿得到身份,就不该绕这一圈。

🩸 **合并成功后整页重载**:后端一次改两条候选(本条内容变长转 `modified`,
下一条转 `rejected`),而审核台没把"重查列表"暴露给渲染器。不刷新的话编辑区还捧着
合并前的文本,此时点「Save changes」会把合并结果**覆盖回去**(丢数据)。
所以先弹 toast,停 1.2s 让人读完,再 `location.reload()`。

## 审核台是怎么复用的

```
chunkActions = {
  approveLabel: 'Keep chunk',     // 审的是"要不要留在索引里",不是判决对错
  requireRejectNote: false,       // 丢一条切片的理由通常是"这页是目录",不值得强填
  publish: true, bulk: true,      // 保留 S0 语义:标 approved → 最后一次性发布整批
  approve / reject                // 与 DEFAULT_ACTIONS 同实现(PATCH /api/staging/{id})
}
```

★ **采纳 ≠ 发布**(与 S1 相反):切片要整份文档一起进索引才有意义,半份文档的向量库
检索出来的答案会缺上下文。`DEFAULT_ACTIONS` 没有导出,只能照抄一份实现;它改了这里要跟着改。

## 我要改 X 去哪

| 改什么                   | 去哪                                         |
| ------------------------ | -------------------------------------------- |
| 候选列表一行显示什么     | `renderers.tsx` 的 `ChunkItemCard`           |
| 切片可编辑哪些字段       | `renderers.tsx` 的 `ChunkItemEditor`         |
| 图表那一栏               | `FigureList.tsx`(挂在 `ChunkOriginPanel` 下) |
| 合并动作的提示与失败文案 | `MergeButton.tsx` 的 `FAILURE_TEXT`          |
| 通过/驳回打哪个接口      | `actions.ts`                                 |
| 文档列表的动作按钮       | `DocumentsPage.tsx` 的 `RowAction`           |
| 上传被拒的文案           | `DocumentsPage.tsx` 的 `UPLOAD_FAILURE_TEXT` |
| stage 的文案与颜色       | `schema.ts` 的 `STAGE_LABEL` / `stageTone`   |
| 图片 / PDF 的地址        | `files.ts`                                   |


## 引用回显(分册 3 §5-6)

答案里那条 `[n]` 由本域整条画:`module.ts` 的 `citations.chunk = ChunkCitation`。
共享的 `components/Citations.tsx` **零改动** —— S3 已经把这个登记口开出来了,
`CITATION_KB` 那条兜底通路走不到。

```
折叠态  蓝点 + [n] + heading_path + 重排分 + 页码        ← 全部来自 citation.extra
展开态  GET /api/document/chunks/{ref_id}               ← 实时读库,不用 extra 里的快照
        ├ 元数据行:文档名 / 页 / chunk #seq / token / Source PDF 外链
        ├ ChunkContent:正文,![](images/…) → <img>
        └ FigureList:与审核台原文对照栏同一个组件
```

🩸 **全文为什么不存在引用里**:存了就是一份会漂移的副本 —— 切片后来被改过,
历史会话点开看到的还是提问那天的样子。实时读库的前提是被引用过的切片不物理删
(下线是软标志,归 S2-4),所以 `ref_id` 永远解析得到;解析不到时退回
`citation.snippet` 那 240 字,并说明这条切片已不在库里。

`readFigure()` 两个来源共用:审核台的 jsonb payload 什么都可能缺,
openapi 生成的 `Figure` 带默认值(TS 里是可选)—— 都在那里补齐。


## 运营两页(S2-4)

```
/ingest/document                          文档列表(上传 / Manage chunks / Retrieval console)
/ingest/document/documents/:id/chunks     切片管理页  → chunks(已发布的正式行)
/ingest/document/search                   检索调试台  → GET /api/document/search
/jobs/:jobId/review                       切片审核台  → staging_items(发布前的候选)
```

🩸 **管理页与审核台是两张表、两套动作**,别搞混:审核台上的「不采纳」发生在发布前、不可逆;
管理页上的「禁用」发生在发布后、可逆(启用要**重算 embedding**,所以那颗按钮必须有 loading 态)。

**退休行**由后端的 `retired` 旗标标出(出处 `chunks.meta.retired`),
**不要自己判 `seq < 0`** —— `seq` 就是它当初的编号,负号区那套编码已经废弃。
退休行没有任何动作:它的正文早被新一版取代,只为历史会话的引用还解析得到而留着。

**seq 空洞是要给人看的。** 审核里被驳回或被合并掉的切片不会让后面的号往前挪,
号码里的洞就是"这里原本有东西"的唯一痕迹 —— 也是"上下文扩展取 seq±1 为什么会跳号"的答案。
`ChunkTable` 在跳号处插一行标记(`chunkOps.gapLabel`),不要把它优化掉。

**调试台的 `guard_fallback`。** 重排整题失灵时系统会**丢掉重排的顺序、保留 RRF 名次** ——
此时列表的排序不是重排给的,分数只是参考。这件事必须显式说出来,否则读者会以为
那一串负分就是最终排序的依据。


## 上传卡的拖拽投放(`useFileDrop.ts`)

两个坑,都是"不写就出事、写了看不出来"的那种:

1. 🩸 **`dragover` 必须 `preventDefault()`**。不拦掉它,浏览器不认这是投放区,
   松手会**直接打开那个 PDF** —— 整页被替换,用户以为程序崩了。
2. 🩸 **用计数器而不是布尔值切高亮**。`dragenter`/`dragleave` 在**子元素之间移动时也成对触发**,
   布尔值会让鼠标经过卡里的按钮时高亮闪烁。

拒收路径要给人话(`unsupported_file_type`),别静默吞掉 —— 拖了个 `.docx` 进来什么都不发生,
比报错更让人困惑。

**为什么没提成共享 hook**:它现在只有本域用。三个域都要的时候再提(**别 import 兄弟域**)。
