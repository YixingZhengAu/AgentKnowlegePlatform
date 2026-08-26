# server/app/services/document/ · architect

## 数据流:一份 PDF 到一条答案

```
上传 PDF
  │  api/document.py::upload_document   建 IngestSource + Document,submit_job("doc_ingest")
  ▼
ingest.py::DocIngestJob                 五步,全自动,末端停在人工审核
  ├ parse     providers/mineru.py::call_mineru → parser.parse_blocks → storage 落图 + parsed.json
  ├ clean     cleaner.clean(去页眉页脚 / 行内 LaTeX 归一化)
  ├ chunk     chunker.build_chunks(标题分节 → 句子边界二次切;图表整块不切)
  ├ describe  describer.describe(唯一 LLM 步骤,把 {{FIGURE:x}} 换成描述 + 图片链接)
  └ stage     StagingItem × N(item_type="chunk"),job → review
  ▼
审核台(共享 /jobs/:jobId/review)        编辑 / 不采纳 / 合并相邻(api/document.py::merge_next)
  ▼
POST /api/jobs/{id}/publish
  │  core/staging.py::publish_job → publisher.py::publish_chunks
  ▼
indexer.replace_document_chunks         chunks 行 + embedding(同一事务);tsv 由数据库生成列自动算
                                        token_count 按最终正文重算(审核台改过正文后 payload 里那个是旧的)
  ▼
问答:core/chat.py 的 stage retrieve_doc_rag → retriever.retrieve → 证据拼进 prompt → generate
  ├ 入选   _doc_rag_used():按答案正文里出现过的 [n] 筛引用(哨兵句 → 零引用)
  └ 校验   verify_doc_rag(默认关):verifier.verify() → 只写进这一跨度的 output
```

## 我要改 X,去哪

| 想改什么 | 去哪 |
| --- | --- |
| 切片大小 / 重叠 | `app/config.py` 的 `doc_rag_chunk_*`(**不要**改 chunker 里的默认值,那是形参兜底) |
| 图表描述的写法 | `describer.py::_system_prompt()` —— 三段式规则全在这一个字符串里 |
| 两条腿各召回多少 / RRF 平滑 | `app/config.py` 的 `doc_rag_vector_topk` / `doc_rag_fts_topk` / `doc_rag_rrf_k` |
| 重排策略与阈值 | `app/providers/cross_encoder_rerank.py` + `doc_rag_rerank_*`(不在本域) |
| 停用词表 | `retriever.py::STOPWORDS` |
| 禁用/启用/重跑的语义 | `api/document.py` 的「运营」一节;退休规则在 `indexer.py::_retire_cited_then_delete_rest` |
| `chunks.meta` 的结构 | `indexer.py::chunk_meta()`,契约出处 `documents/DB-DESIGN.md` §3 |
| 落盘目录 | `storage.py` —— 唯一路径出处,别的文件不许拼路径 |
| 摄取的步骤数与名字 | `ingest.py::DocIngestJob.steps`(前端 `<JobProgress>` 自动跟着变) |

## 几处会咬人的地方

**① `Chunk.as_payload()` 必须自成一体。** 发布(`publisher.py`)与"合并相邻"(`api/document.py`)
都是拿 `staging_items.payload` 反过来 `Chunk.model_validate()` 的。
2026-08-25 实测:漏了 `page_idx` → merge-next 直接 500。`origin_ref` 那份页码是给审核台跳原文用的,
不是它的替代品。断言在 `tests/test_document_chunker.py::test_payload_round_trips`。

**② publisher 拿到的不是全集。** `core/staging.py` 只把**这一轮**新通过的候选交给 publisher
(`not i.published`)。照它给的那批做"全删重建"会把上一轮已发布的切片一起抹掉 ——
所以 `publish_chunks` 自己回查该文档全部通过审核的候选再整体重建。

**③ 关键词腿的两个坑必须同时躲开。** `plainto_tsquery` 是 AND 语义,而 `simple` 分词器不去停用词,
自然语言问题命中 0 条;改成 OR 又命中几乎全库,而 `ts_rank` 没有 IDF。
解法是**自己去停用词再 OR**(`retriever.keyword_terms`)。这条对生产同样成立。

**④ 候选必须按 RRF 名次交给重排。** `cross_encoder_rerank` 的 `guard` 策略在整题失灵时
**原序返回** —— 靠的就是传进去的那个顺序。打乱了,guard 退回的就不是召回名次而是噪声。

**⑤ 标题文本要进 `content`。** `chunks.tsv` 是 `to_tsvector('simple', content)` 生成列(已定不改),
只索引 `content`。标题只写进 `heading_path` 的话,标题里的词从关键词索引里彻底消失。
`chunker.split_sections` 因此把标题块留在该节正文的第一位。

**⑥ 合并之后别再"全选通过"。** 合并把被并走的那条标成 `rejected`。
审核台的批量操作是 S0 的通用能力,一次"全选 → Approve"会把它重新改回 `approved`,
于是那段正文在两片里各出现一次。这不是代码 bug(通用批量本来就该照用户说的做),
但演示时要注意顺序:**先批量通过,再逐条合并**。

**⑦ 生成后校验不许弄丢答案。** `verify_doc_rag` 跑在 `_persist` **之前**,
而 `chat_events` 的外层只接住取消类异常 —— 它抛出去,这次问答的助手消息与 trace 一起没落库。
2026-08-25 实测踩过(verifier 里写错了 `LLMResult` 的字段名)。
所以 `verifier.verify()` 内部与 `chat.py` 里那一块**各兜一道 `except Exception`**,
一个默认关着的诊断开关没资格让用户丢一个已经答完的回答。

**⑧ 重新发布时,被引用过的旧行退休而不是删。** `message_citations.ref_id` 是弱引用(没有外键),
删掉不报错,只会让历史会话里那条引用点开变成"这条切片已不在库里"。
退休 = `disabled` + 清向量 + `meta.retired=true`,**`seq` 原样保留**;
唯一约束是"只管 active 行"的部分索引,所以退休行与新一代的同号行可以并存。
判据用 `meta.retired` 而不是 `status`:`disabled` 有两个来源,人手点的「禁用」(可逆)
与退休(不可逆),前端要分开显示。

> ⚠ 曾经用"把退休行 seq 挪进负号区"绕开全表唯一约束,那套编码**跨代不唯一** ——
> 同一个 seq 退休两次撞同一个槽,实测直接炸。**别为绕开约束发明编码,把约束改对。**

**⑨ ~~本阶段没有 `chunks.status`~~(已加,S2-4)。** 当初推迟时说好要一起做三件事
(加列 / **两条召回 SQL 都补 `status='active'` 过滤** / 禁用时清空 embedding),
三件全部落地,出处 `documents/DB-DESIGN.md` §3。

## 与共享层的接触面(PR 要重点说明)

- `app/services/__init__.py` 一行(Job 注册,预留行取消注释)
- `app/api/__init__.py` 一行 + `app/api/document.py` 新文件
- `app/core/chat.py`:插入 stage `retrieve_doc_rag`(契约变更 C1),并把 text2sql 的
  `refused_non_data` 分支从"直落 generate"改成"先走文档 RAG"
- `app/providers/mineru.py`(C3,MinerU 客户端上提)、`app/providers/base.py`(C6,图文混排消息)
