# server/migrations/architect.md

## 当前版本链

- `184b03b23dab` initial schema:30 张表一次建齐(D4:改表比建表贵)
  - 开头 `CREATE EXTENSION IF NOT EXISTS vector / pgcrypto`,让迁移自成一体(不依赖 docker init 脚本)
  - 向量列维度用模块级 `EMBEDDING_DIM = settings.embedding_dim`,**不硬编码**
  - HNSW 索引通过 `postgresql_using='hnsw'` + `postgresql_ops={'embedding':'vector_cosine_ops'}` 落地

- `s3a1b2c3d4e5` S3 智能问数:语义层重审 + 已验证意图四张新表(手写,没跑 autogenerate)
  - 新建 `sql_intents` / `intent_questions` / `non_data_faces` / `intent_vectors`;
    删除 `metrics` / `terms` / `rules` / `sql_examples`(理由见 DB-DESIGN §4.9,净数仍是 30 张)
  - `intent_vectors.intent_id` **可空**(NULL = 空路由伪意图),配一条
    `CHECK ((face_kind='non_data') = (intent_id IS NULL))` 防出现"挂在真意图上的负例面"
  - 碰了共享表 `staging_items` 的 item_type CHECK(加 `sql_intent`,去掉 table_meta/metric/term)
    —— 必要的契约变更,不是"顺手加自己需要的列"
  - **upgrade / downgrade 双向都实测跑过**;downgrade 会按 initial 的定义重建那四张废弃表
    (内容无法恢复,它们本来一直是空的)

## 改表流程(详见 DB-DESIGN §10)

| 情形 | 改法 |
| --- | --- |
| 表还是空的 | 直接改 initial migration -> `make db-reset` |
| 有数据但可重灌 | 改 model -> `uv run alembic revision --autogenerate` -> **人工审查** -> `make migrate` |
| 只改 jsonb 内部结构 | 只改 Pydantic schema,零 migration |

## 自检

`cd server && uv run alembic check` 应输出 "No new upgrade operations detected."
(模型与库不一致会在这里暴露。`chunks.tsv` 的 Computed 警告是正常的,可忽略。)
