# server/app/services/document/

**职责**:文档 RAG(Document RAG)知识域的全部后端逻辑 —— 解析、清洗、切分、图表描述、检索、发布。
逻辑本身在 S2 沙箱(`tmp/s2-dev/`,已完成 Step 1–5)里逐步实测调优,这里是平移落点:
**沙箱逻辑一行不改,只换三处底座** —— 直调 openai → Provider 层、内存索引 → pgvector、文件与 CLI → Job 框架 + 数据库。

| 文件 | 说明 |
| --- | --- |
| `storage.py` | 落盘位置(唯一路径出处)+ 图片 URL 改写 + 清盘;**目录与 S1 逐字相同**,为的是白拿 `api/files.py` 的图片出口 |
| `parser.py` | M1:MinerU 产物 → 结构化块;未知类型只计数不抛异常;用栈推导 `heading_path` |
| `latex_inline.py` | 行内 LaTeX 归一化(MinerU 会把 `−20 °C` 判成公式吐 LaTeX) |
| `cleaner.py` | M2:跨页重复的页眉页脚 / 纯页码 / 空行残留,丢弃一律计数 |
| `chunker.py` | ★ M3 质量地基:按标题分节 + 句子边界二次切 + 图表整块不切;参数 `512/80` 定稿 |
| `llm.py` | 结构化输出适配(Provider `json_schema` → Pydantic);**支持图文混排 user 消息**(契约变更 C6) |
| `describer.py` | M4:整条摄取链**唯一调 LLM** 的一步;三段式描述(LEAD/COVERAGE/VALUES)固化在 system prompt |
| `indexer.py` | 索引面维护:`chunks` 行 + embedding,重建时**被引用过的旧行退休而非删除**,**不 commit** |
| `retriever.py` | M6 混合检索:向量腿 + 全文腿 → RRF(k=60) → 重排 Top-5 → 按 seq 扩上下文 |
| `verifier.py` | 生成后的一致性校验(`DOC_RAG_VERIFY`,默认关);**只写轨迹,不改答案** |
| `publisher.py` | `@register_publisher("chunk")`:批量发布,一份文档一次全删重建 |
| `ingest.py` | `doc_ingest` 一个 Job 五步:parse / clean / chunk / describe / stage |
| `__init__.py` | 只做一件事:import `publisher` 触发注册 |

**纪律**:不 import 兄弟域;只向上依赖 `app/core` / `app/models` / `app/schemas` / `app/providers`。
契约(字段名)在 `app/schemas/document.py`,本目录不另定数据形状。

**离线单测**(切分与解析改错了不报错,只是安静地给出更差的答案):
`server/tests/test_document_{parser,chunker,retriever}.py`。
接口在 `app/api/document.py`;图片出口复用 `app/api/files.py`。

详见 `architect.md`。
