# web/src/domains/document/

**职责**:文档 RAG(document)域前端 —— 上传 / 切片审核 的一切代码都落在这里。

| 文件                | 说明                                                                             |
| ------------------- | -------------------------------------------------------------------------------- |
| `module.ts`         | 域描述符(路由 `/ingest/document`、识别色蓝、`chunk` 渲染器 + 动作登记)           |
| `IngestPage.tsx`    | 域内路由壳(本域只有 index 一页;审核走共享 `/jobs/:jobId/review`)                 |
| `DocumentsPage.tsx` | 首页:上传 PDF + 文档列表(stage / 页数 / 切片数 / 一行一个动作 + 删除)            |
| `ChunksPage.tsx`    | **切片管理页**(S2-4):已发布正式行的列表 + 禁用/启用 + 重跑入口          |
| `ChunkTable.tsx`    | 管理页的表:seq 空洞标记 + 退休行分区                                    |
| `ChunkRow.tsx`      | 管理页的一行:向量态/状态徽标、禁用启用(启用有 loading)、展开看全文     |
| `ReingestCard.tsx`  | 单文档重跑:两步确认(不用 `window.confirm`,原生弹窗会卡住自动化)      |
| `chunkOps.ts`       | 管理页纯逻辑:错误码文案、seq 空洞、正文预览                             |
| `SearchConsolePage.tsx` | **检索调试台**(S2-4):问一句 → 两条腿 / RRF / 重排都看得见           |
| `RecallStrip.tsx`   | 调试台顶部:两条腿与融合的条数 + guard 触发时的警告横幅                  |
| `SearchHitRow.tsx`  | 调试台的一条结果:各腿名次(没召回显示成虚线 chip)+ 展开看全文          |
| `renderers.tsx`     | `chunk` 审核渲染器(卡片 / 编辑器 / 原文对照)                                     |
| `Citation.tsx`      | 答案里那条 `[n]` 引用(登记在 `module.ts` 的 `citations`):展开时**实时读库**取全文 |
| `ChunkContent.tsx`  | 切片正文渲染:把 `![](images/…)` 换成真实截图,其余原样            |
| `FigureList.tsx`    | 原文对照栏里的图表清单(只读:图 + 描述 + 截断标记)                                |
| `MergeButton.tsx`   | 「Merge with next」动作:`POST /candidates/{id}/merge-next`                       |
| `actions.ts`        | 审核动作层:保留 S0 批量发布语义,只换 `Keep chunk` + 驳回理由选填                 |
| `useFileDrop.ts`    | 把一块区域变成文件投放区(上传卡的拖拽);计数器防闪 + 必须拦 `dragover` |
| `files.ts`          | 静态产物 URL 拼装(图片 / 原件 PDF),`<img>` `<iframe>` 不走 `apiFetch`            |
| `schema.ts`         | 生成类型的短名 + stage 文案/色 + jsonb 读取工具(**不手写 API 类型**)             |

详见 `architect.md`;跨域约定见 `../claude.md`。
