# server/app/services/exact_qa/architect.md

## 定位

精准问答域(S1)的落点。本域的解析、抽取、相似问生成、检索、发布、Job、prompt
**全部写在这里**,不散落到 core。

## 沙箱 → 集成的对应关系(逻辑不再改,只换三样东西)

S1 沙箱阶段每个模块都在 CLI 里实测调优过(沙箱已删,结论在 `documents/S1-PLAN.md` §5),集成只做三处替换:
**openai 直调 → Provider 层**、**内存 numpy 索引 → pgvector**、**json 文件交接 → Job scratch + 库**。

| 沙箱脚本 | 本目录落点 | 换掉了什么 |
| --- | --- | --- |
| `schemas.py` | `app/schemas/exact_qa.py` + 本目录 `storage.py` | 路径常量从契约里拆出来 |
| `parse_pdf.py` | `parser.py` ✅ | httpx 同步 → 异步;落盘目录 → FILE_STORAGE_DIR |
| `extract_qa.py` | `extractor.py` ✅ + `matching.py` | openai → `get_llm()` main tier |
| `gen_similar.py` | `similar_gen.py` ✅ | openai → light tier;线程池 → asyncio 信号量 |
| `retrieve_qa.py` | `retriever.py` ✅ + `indexer.py` ✅ | numpy 内存矩阵 → pgvector |
| (无沙箱落点) | `publisher.py` ✅ | 采纳即发布的事务与状态流转 |

## matching.py:为什么单独一层

同一道"**区分性 token**(含数字的词)必须一致"的保险,在本域被用了三次:
M2 判重(阈值 0.70)、M3 跨条冲突(0.75)、M4 命中护栏(看差集)。
它不是锦上添花,是两个真 bug 逼出来的 —— 判重误杀 ResNet-152 那条(静默丢知识)、
「416×416」以 0.827 命中「320×320」那条(把错答案标成 Verified Answer)。
所以三处共用一份实现,改一处就得改全部,单测钉在 `tests/test_exact_qa_matching.py`。

## parser.py:块类型只认"内容集合",陌生类型不许打死整篇解析

`content_list` 是 **MinerU 的输出**,不是我们的入参 —— 所以 `ContentBlock.type` 是 `str`,
**不做枚举收窄**。判断集中在 `app/schemas/exact_qa.py` 的两个集合:

- `CONTENT_BLOCK_TYPES` = text / table / image / chart / equation
  —— `build_paged_md()` 里每种都有对应分支,只有它们会进 markdown
- `NOISE_BLOCK_TYPES` = aside_text / page_number / header / footer / discarded(已知页边噪声)
- `is_noise` 判的是"**不在内容集合里**",所以 MinerU 新冒出来的类型自动按噪声丢掉,不抛异常;
  `is_unknown_type`(不在上面两个集合里)只用来留痕

留痕有两处,缺一不可 —— 丢块是静默失败,没有痕迹就等于内容悄悄少了:
`ingest.step_parse` 打 `log.warning("mineru_unknown_block_types")` 并把类型写进 step log;
`parser.dropped_by_type()` 按类型计数进 `ParseStats.dropped_by_type`,store 步的 message
与文档 `meta.parse_stats` 都带上(如 `dropped 23 noise: footerx5, headerx13, page_numberx5`)。

**为什么这么写**:原来 `type` 是 `Literal[...]`,枚举取自沙箱那份 arXiv 论文的 7 种类型。
真实公司政策 PDF 有页眉页脚,`header` 不在枚举里 → `model_validate` 抛 ValidationError →
一个页眉块把整篇文档打成 `parse failed`(2026-08-23 实测,详见 `documents/S1-PLAN.md` §9.1)。
回归钉在 `tests/test_exact_qa_parser.py`。

## llm.py:结构化输出为什么要过 Provider

沙箱用 openai SDK 的 `responses.parse(text_format=Model)` 一行拿对象;
Provider 层给的是 `complete(json_schema=...)` + `LLMResult.data`,差的一层在 `llm.py` 补。
不绕过 Provider 的三个理由:型号只由 `.env` 的 tier 映射决定 /
重试与异常翻译不重复实现 / 每次调用产出 usage 与 cost(trace 面板才有数)。

## 已落地:storage.py

FILE_STORAGE_DIR 下的目录形态与四个固定落点(文件名常量在 schemas,位置在这里):

```
parses/{document_id}/
  paged.md           带页标记的解析文本(校对对象 / M2 输入)
  reviewed.md        校对后文本(存在则 M2 用它;paged.md 永远保留)
  parse_result.json  页尺寸 + 块序列 + 统计
  images/*.jpg
```

- `source_md()` 实现"有 reviewed.md 用它、没有退回 paged.md"的契约(S1-plan §8.3b)
- `remove_document_files()` 删文档时清盘(整个 `parses/{id}/` + `sources/{id}.pdf`)。
  **库里事务成了才动磁盘,且删不掉只记 warning** —— 反过来会出现"文件没了行还在"
- `rewrite_image_urls()` 把 md 里的 `images/x.jpg` 改写成
  `/api/files/parses/{id}/images/x.jpg`。**改写只在后端出口做,入库一律存相对路径**
  —— 同一段文本被校对页、审核台、对话消息多处消费,集中改写才不会漏

## 三个配置项(app/config.py,Step 5 实测定稿)

| 配置 | 值 | 含义 |
| --- | --- | --- |
| `EXACT_QA_HIT_THRESHOLD` | 0.55 | 余弦 ≥ 此值才可能命中(**不是 0.90**:正例实测只有 0.61–0.91) |
| `EXACT_QA_BORDERLINE_THRESHOLD` | 0.40 | 低于此值直接 MISS |
| `EXACT_QA_HIT_GATE` | true | 命中前用 light 模型复核一次 |

阈值只切得开"越界问题"(0.13–0.38),切不开"同领域但原文没答案"(0.61–0.83)——
后者靠两道与阈值正交的关:**区分性 token 护栏**(纯代码)+ **light 模型复核**。
改这三个值前先读 `documents/S1-PLAN.md` §5 M4(三种配置的实测对比)。

### 复核关的取向(`GATE_PROMPT`,Step 8 改过一次)★

**它只判"这答案答的是不是这个问题",不给答案质量打分。** 答案是人工采纳过的,
措辞与详略程度已经定了,再让 light 模型评一遍就会挡下合法命中 —— Step 7/8 实测被
误否决过两次:一次理由是"过于简略(没展开损失函数)",一次是"含糊(没给确定的 GPU)",
而后者的原文本身就不确定。两条都是答案对、人已采纳,阈值也调不动它(0.8866 与 0.9244)。

现在的 prompt 明确写了**不构成否决的理由**:简短、含糊、少了用户没问的细节、风格朴素。
否决只留给"答的是另一个对象/另一个方面"(邻近实体、不同分辨率、不同型号)。
用例表固化在 `scripts/smoke_exact_qa.py` 第 ④ 步(两条误否决案例 + 两条邻近实体),
再动这段 prompt 就跑它。

## 红线

- **不 import 兄弟域**,只向上依赖 `app/core`、`app/models`、`app/schemas`
- Job 子类的注册行加在 `app/services/__init__.py`(全局唯一注册点)
- 共享表(`ingest_jobs`/`staging_items`/`publish_records`/`knowledge_bases`)不加本域私有列

## 采纳即发布(publisher.py)

```
staging_items(review) ──点「采纳」──▶ exact_qa_items + exact_qa_vectors(一问一行)
                                     staging.published=true / published_ref={table,id,index_faces}
                     ──点「不采纳」─▶ review_status=rejected(理由必填,留痕不入库)
   全部候选裁决完(没有 pending)──▶ job.status=published + 一条 publish_records(漏斗数字)
```

- **一个事务**:写正式表与建向量索引同生共死 —— 否则会留下"永远命不中的知识",界面上看不出来
- 幂等:已发布的候选再点采纳直接返回原 `published_ref`,不写第二份
- `@register_publisher("qa_pair")` 仍然注册:批量入口 `POST /api/jobs/{id}/publish` 与逐条采纳
  复用同一个 `_publish_one()`,不会出现"批量发的那批没有向量"的半残状态
- 下线 = `status=disabled` + 删向量行;**正式行不物理删**(被 `message_citations.ref_id` 引用过)

## 检索的索引面与分数(indexer.py / retriever.py)

- 索引面 = 标准问 + 每条相似问,各一行;item 得分 = 各面得分的最大值
- 答案不进索引(拿答案匹配问题会把"答案里恰好出现的词"当召回信号)
- 余弦相似度 = `1 - cosine_distance`,HNSW 索引建在 `vector_cosine_ops` 上。
  **这是"内存索引换 pgvector"唯一真会出错的地方**,由
  `scripts/smoke_exact_qa_store.py` 的 1e-3 断言守着(实测偏差 2.85e-07)
- ⚠ 实测:**OpenAI embedding 跨批次不确定**(同句不同 batch 余弦 0.99942)。
  所以对数必须读回库里存的那份向量;也因此**阈值只在 ±0.005 尺度上有意义**
- `origin_ref` 不复制进正式表:经 `source_staging_id` 回 `staging_items.origin_ref` 取,
  少一处会不同步的数据

## 两个 Job 与那道人工关(ingest.py)

```
上传 PDF ──▶ qa_parse ──▶ 待校对 ──(人工校对 + 点「确认,开始抽取」)──▶ qa_extract ──▶ 候选待采纳
             fetch / parse / store                                     extract / similar / stage
             terminal=published(不产待审)                              terminal=review(等人采纳)
```

**为什么拆两个 Job**:中间夹着人工关,一个 Job 停不下来;而且解析失败(重跑 MinerU)
与抽取失败(重花 LLM 的钱)要能各自重跑,混在一起重跑就是浪费。

- `params` 只放 `{"document_id": ...}`;job 之间的衔接靠 `documents.meta` 里的
  `parse_job_id` / `extract_job_id`(不加列,见 §红线)
- 失败时把错误也落到**文档**上:文档列表是用户唯一入口,只写 job.error 的话
  列表那一行会永远显示"解析中"
- `qa_extract` 失败不改 `parse_status`(解析是好的),错误写进 `meta.extract_error`
- `stage` 步骤幂等:重跑不会把候选写两遍

## 文档状态怎么来的

`documents.parse_status` 只有 4 态(pending/parsing/parsed/failed),
界面要的"待校对 / 抽取中 / 待采纳 / 已完成"是**推导态** `DocumentOut.stage`
(`api/exact_qa.py::_stage`),由解析态 + 抽取 Job 状态 + 漏斗 pending 数推出来。
不扩 CHECK 枚举 = 少一处会不同步的状态(S1-plan §8.4 方案 A)。

## 接口分工:什么进域接口,什么走通用审核接口

| 走通用(`/api/staging`) | 走域接口(`/api/exact-qa`) |
| --- | --- |
| 列候选、筛选、编辑 payload、批量改状态 | 上传、校对文本读写、确认抽取、采纳/不采纳、正式 QA 管理 |
| 理由:三类知识是同一套审核流程 | 理由:采纳=写正式表+建向量,不是纯状态变更 |

图片出口 `GET /api/files/parses/{document_id}/images/{name}` 在 `app/api/files.py`,
只允许单层文件名(路径穿越是这类端点最常见的洞,冒烟脚本里有反例断言)。
