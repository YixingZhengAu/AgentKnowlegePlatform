# server/app/services/exact_qa/

**职责**:精准问答(Exact Q&A)知识域的全部后端逻辑 —— 解析、抽取、相似问、检索、发布。
逻辑本身在 S1 沙箱里已逐个实测调优(沙箱已删,见 `documents/S1-PLAN.md` Step 0–5),这里是平移落点。

| 文件 | 说明 |
| --- | --- |
| `matching.py` | ★ 文本比对纯函数:词集 Jaccard + **区分性 token** 保险(判重/冲突/护栏三处共用) |
| `storage.py` | 解析产物落盘位置(唯一路径出处)+ 图片 URL 改写 + reviewed/paged 取文契约 + 删文档清盘 |
| `llm.py` | 结构化输出适配:Provider 的 `json_schema` 模式 → Pydantic 对象(三个调用点共用) |
| `parser.py` | M1:HTTP 调常驻 mineru-api + 拼 `paged.md` + 页尺寸/统计 |
| `extractor.py` | M2:gpt-5 抽候选 QA + quote 逐字定位/修复 + bbox 回填 + 硬约束过滤 |
| `similar_gen.py` | M3:gpt-5-mini 生成相似问 + 与标准问同/跨条冲突两道过滤 |
| `retriever.py` | M4:分档纯函数 `decide_tier()` + light 复核 `gate_hit()`(**只判是否答了这个问题,不给答案质量打分** —— 见 architect)+ pgvector 检索 `retrieve()` |
| `indexer.py` | 索引面维护:一问一行、问题集合一变就全删重建;下线=删向量行 |
| `publisher.py` | **采纳即发布**:候选 → `exact_qa_items` + 向量(一个事务);逐条采纳/不采纳/下线 |
| `ingest.py` | 两个 Job:`qa_parse`(fetch/parse/store)与 `qa_extract`(extract/similar/stage) |
| `__init__.py` | 只做一件事:import `publisher` 触发 `@register_publisher("qa_pair")` |

**纪律**:不 import 兄弟域;只向上依赖 `app/core` / `app/models` / `app/schemas`。
契约(字段名)在 `app/schemas/exact_qa.py`,本目录不另定数据形状。

**离线单测**(S1 唯一必须写单测的地方,因为改错了不报错只是静默给错答案):
`server/tests/test_exact_qa_{matching,extractor,similar,retriever,parser}.py`
(`parser` 那份是 2026-08-23 的回归:MinerU 冒出的块类型不许再打死整篇解析,见 S1-PLAN §9.1)。
联网通路用 `server/scripts/smoke_exact_qa.py`(三个 LLM 调用点)与
`server/scripts/smoke_exact_qa_store.py`(存储层 + **pgvector 分数与手算余弦对数**)、
`server/scripts/smoke_s1_api.sh`(HTTP 全链路 13 步)。
接口在 `app/api/exact_qa.py`(域接口)与 `app/api/files.py`(图片出口)。

详见 `architect.md`。
