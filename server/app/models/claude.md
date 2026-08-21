# server/app/models/

**职责**:全部 SQLAlchemy 模型;字段级定义的唯一出处是 `documents/DB-DESIGN.md`,改表先改文档。

| 文件 | 表 |
| --- | --- |
| `base.py` | `Base`、`UUIDMixin` / `CreatedAtMixin` / `TimestampMixin`、`enum_check()` |
| `_types.py` | `embedding_column_type()`:维度读 `EMBEDDING_DIM`,不硬编码 |
| `user.py` | users(+ `DEFAULT_USERNAME`) |
| `knowledge.py` | knowledge_bases |
| `exact_qa.py` | exact_qa_items / exact_qa_vectors |
| `document.py` | documents / chunks |
| `text2sql.py` | datasources / table_meta / column_meta / relations / metrics / terms / rules / sql_examples |
| `ingest.py` | ingest_sources / ingest_jobs / staging_items / publish_records |
| `agent.py` | agents / agent_kb_bindings |
| `conversation.py` | conversations / messages / message_citations |
| `observability.py` | traces / feedbacks / unanswered_pool |
| `evaluation.py` | eval_sets / eval_cases / eval_runs / eval_results |
| `__init__.py` | 汇总导出(**新增模型必须在这里导出**,否则 alembic 当它是待删表) |

详见 `architect.md`。
