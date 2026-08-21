# server/app/models/architect.md

共 30 张表。

## 约定(来自 DB-DESIGN.md §0)

- 主键:`UUIDMixin` -> `gen_random_uuid()` 由 DB 生成
- 时间:`CreatedAtMixin`(只有 created_at)/ `TimestampMixin`(带 updated_at,SQLAlchemy onupdate 维护)
- 枚举:`enum_check("status", STATUSES, "ck_xxx_status")` 生成 `text + CHECK`,**不用 PG native enum**
  - 每个模型文件顶部把取值定成模块级常量(如 `JOB_STATUSES`),业务代码引用常量而不是写字面量
- 向量列:`embedding_column_type()`,HNSW + `vector_cosine_ops`
- 外键:附属子表 CASCADE;溯源弱引用 SET NULL(如 `exact_qa_items.source_staging_id`)

## 需要特别注意的地方

- `chunks.tsv`:`Computed("to_tsvector('simple', content)", persisted=True)` 生成列 + GIN 索引。
  S0 用 `simple` 占位,S2 评估分词方案时改这里(改生成列 = 改 migration)。
- `exact_qa_vectors`:UNIQUE `(item_id, question_text)`。item 的问题集合变化时,
  **应用层全删重建该 item 的向量行**(简单且不会漏)。
- `ingest_jobs.heartbeat_at` + `JOB_HEARTBEAT_TIMEOUT_SEC=60`:启动时把
  「running 且心跳超时」的置 failed(僵尸任务处理,Step 7 实现)。
- `message_citations.ref_id` 是弱引用,故意不建 FK(可能指向 exact_qa_items 也可能指向 chunks)。
- jsonb 字段(payload / meta / extra / route_decision …)的内部结构由 Pydantic 校验,
  改结构零 migration,见 DB-DESIGN §8 / §10。
