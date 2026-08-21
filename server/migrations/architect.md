# server/migrations/architect.md

## 当前版本链

- `184b03b23dab` initial schema:30 张表一次建齐(D4:改表比建表贵)
  - 开头 `CREATE EXTENSION IF NOT EXISTS vector / pgcrypto`,让迁移自成一体(不依赖 docker init 脚本)
  - 向量列维度用模块级 `EMBEDDING_DIM = settings.embedding_dim`,**不硬编码**
  - HNSW 索引通过 `postgresql_using='hnsw'` + `postgresql_ops={'embedding':'vector_cosine_ops'}` 落地

## 改表流程(详见 DB-DESIGN §10)

| 情形 | 改法 |
| --- | --- |
| 表还是空的 | 直接改 initial migration -> `make db-reset` |
| 有数据但可重灌 | 改 model -> `uv run alembic revision --autogenerate` -> **人工审查** -> `make migrate` |
| 只改 jsonb 内部结构 | 只改 Pydantic schema,零 migration |

## 自检

`cd server && uv run alembic check` 应输出 "No new upgrade operations detected."
(模型与库不一致会在这里暴露。`chunks.tsv` 的 Computed 警告是正常的,可忽略。)
