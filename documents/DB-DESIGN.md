# 数据库字段级设计(DB-DESIGN)

**用途**:Step 2 写 Alembic migration 的直接输入;之后所有阶段查字段定义的唯一出处。
**关联**:PRD.md §7(表清单)、S0-PLAN.md Step 2。表结构变更时必须同步更新本文档。

---

## 0. 全局约定

| 约定 | 内容 | 理由 |
| --- | --- | --- |
| 主键 | 全部 `id uuid PRIMARY KEY DEFAULT gen_random_uuid()` | 分布式友好、前端可提前生成、演示时不暴露数据量 |
| 时间戳 | `created_at timestamptz NOT NULL DEFAULT now()`;有更新语义的表加 `updated_at`(SQLAlchemy `onupdate` 维护) | 统一,不再逐表说明 |
| 枚举 | 一律 `text + CHECK 约束`,不用 PG native enum | native enum 加值要 `ALTER TYPE`,演进贵;CHECK 改约束即可 |
| jsonb | 默认 `'{}'::jsonb` 或 `'[]'::jsonb`;结构在本文档"payload 结构"节定义,由 Pydantic schema 校验 | DB 不校验 json 内部结构,校验放应用层 |
| 向量列 | `vector(EMBEDDING_DIM)`,维度由 env 读入 migration;索引统一 HNSW + `vector_cosine_ops` | 换 embedding 供应商 = 重建向量列 + 重嵌入(提供脚本),这是有意为之的显式成本 |
| 外键删除策略 | 纯附属子表(vectors/chunks/staging_items 等)`ON DELETE CASCADE`;跨域引用(如 trace→message)`CASCADE`;溯源类弱引用(如 source_message_id)`SET NULL` | 附属数据随主体走;溯源断了不影响主体 |
| 命名 | 表名 snake_case 复数;布尔用 `is_` / `enabled`;外键列 `<单数>_id` | — |
| 软删除 | 不做统一软删除;业务上需要"停用"的表用 `status` 字段 | 演示系统,简单优先 |

---

## 1. 基础域

### users(S0 单行占位)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| username | text | NOT NULL, UNIQUE | seed 写入 `default_user` |
| display_name | text | | 界面显示名 |

### knowledge_bases

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| name | text | NOT NULL | |
| type | text | CHECK IN ('exact_qa','document','text2sql') | 知识库三类型,建库后不可改 |
| description | text | | 也会喂给 S4 路由 LLM 参考 |
| owner_id | uuid | FK→users | |
| status | text | CHECK IN ('active','archived') DEFAULT 'active' | |
| created_at / updated_at | timestamptz | | |

索引:`(owner_id)`。

---

## 2. 精准 QA 域

### exact_qa_items(正式表,发布后数据在这)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| standard_question | text | NOT NULL | 标准问 |
| answer | text | NOT NULL | 命中 ≥0.90 时原样返回、零改写的那个答案 |
| similar_questions | jsonb | DEFAULT '[]' | string[],相似问列表 |
| keywords | text[] | DEFAULT '{}' | 运营检索用 |
| effective_from / effective_to | date | NULL | 有效期,NULL=不限;检索时过滤过期条目 |
| status | text | CHECK IN ('enabled','disabled') DEFAULT 'enabled' | |
| source_staging_id | uuid | FK→staging_items ON DELETE SET NULL | 溯源:来自哪条审核记录 |
| version | int | DEFAULT 1 | 每次编辑 +1 |
| created_at / updated_at | timestamptz | | |

索引:`(kb_id, status)`。

### exact_qa_vectors(一问一向量:标准问 + 每个相似问各一行)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| item_id | uuid | FK→exact_qa_items ON DELETE CASCADE | |
| question_text | text | NOT NULL | 被向量化的那句问题原文 |
| embedding | vector(DIM) | NOT NULL | |
| created_at | timestamptz | | |

约束:UNIQUE `(item_id, question_text)`。索引:HNSW `(embedding)`、`(item_id)`。
**维护规则**:item 的问题集合变化时,由应用层全删重建该 item 的向量行(简单且不会漏)。

---

## 3. 文档 RAG 域

### documents

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| source_id | uuid | FK→ingest_sources ON DELETE SET NULL | 原始上传文件 |
| name | text | NOT NULL | 展示名 |
| file_type | text | CHECK IN ('pdf','docx','md','txt','html','xlsx') | |
| raw_uri | text | | 本地存储路径(FILE_STORAGE_DIR 下相对路径) |
| size_bytes | bigint | | |
| parse_status | text | CHECK IN ('pending','parsing','parsed','failed') DEFAULT 'pending' | |
| parse_error | text | | |
| meta | jsonb | DEFAULT '{}' | 页数、作者等解析元信息 |
| created_at / updated_at | timestamptz | | |

索引:`(kb_id)`。

### chunks

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| doc_id | uuid | FK→documents ON DELETE CASCADE | |
| seq | int | NOT NULL | 文档内顺序,上下文扩展(取前后块)靠它 |
| content | text | NOT NULL | 切片正文 |
| heading_path | text | | 如 `安装手册 > 3 接线 > 3.2 直流侧`,拼进 embedding 输入 |
| summary | text | | 离线生成的块摘要 |
| hypo_questions | jsonb | DEFAULT '[]' | string[],离线 HyDE 假设性问题 |
| token_count | int | | |
| embedding | vector(DIM) | | |
| tsv | tsvector | GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED | S0 用 simple 占位,S2 评估中文分词方案(届时改此生成列) |
| meta | jsonb | DEFAULT '{}' | 页码、bbox 等定位信息(引用跳原文用) |
| created_at | timestamptz | | |

约束:UNIQUE `(doc_id, seq)`。索引:HNSW `(embedding)`、GIN `(tsv)`、`(doc_id)`。

---

## 4. 智能问数域(语义层即知识)

### datasources

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| name | text | NOT NULL | |
| db_type | text | CHECK IN ('postgres') DEFAULT 'postgres' | 演示只支持 PG |
| dsn_enc | text | NOT NULL | 连接串,Fernet 对称加密,密钥来自 env `SECRET_KEY` |
| readonly_confirmed | boolean | DEFAULT false | 运维确认该账号只读;false 时问数功能拒绝执行 |
| status | text | CHECK IN ('active','disabled') DEFAULT 'active' | |
| created_at / updated_at | timestamptz | | |

### table_meta

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| datasource_id | uuid | FK→datasources ON DELETE CASCADE | |
| schema_name | text | DEFAULT 'public' | |
| table_name | text | NOT NULL | |
| display_name | text | | 中文名,如"订单表" |
| description | text | | 给 LLM 的表用途说明 |
| enabled | boolean | DEFAULT true | 是否纳入问数范围(治理开关) |
| row_count_estimate | bigint | | schema 同步时统计 |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(datasource_id, schema_name, table_name)`。

### column_meta

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| table_meta_id | uuid | FK→table_meta ON DELETE CASCADE | |
| column_name | text | NOT NULL | |
| data_type | text | | 同步时抓取 |
| display_name / description | text | | 治理录入 |
| is_sensitive | boolean | DEFAULT false | true 时生成的 SQL 禁止 SELECT 此列 |
| enum_values | jsonb | NULL | 低基数列取值字典,如 `["华东","华南"]`,直接进 prompt |
| sample_values | jsonb | NULL | 同步时采样 3–5 个值,帮 LLM 理解格式 |
| enabled | boolean | DEFAULT true | |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(table_meta_id, column_name)`。

### relations(join 提示)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| datasource_id | uuid | FK→datasources ON DELETE CASCADE | |
| from_table / from_column / to_table / to_column | text | NOT NULL | |
| relation_type | text | CHECK IN ('many_to_one','one_to_one') | |
| description | text | | |

### metrics(指标口径)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| name | text | NOT NULL | 如"销售额" |
| aliases | jsonb | DEFAULT '[]' | string[],如 ["营收","GMV"] |
| definition_sql | text | NOT NULL | 如 `SUM(oi.qty * oi.unit_price)` |
| unit | text | | 元 / 台 / % |
| description | text | | |
| status | text | CHECK IN ('enabled','disabled') DEFAULT 'enabled' | |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(kb_id, name)`。

### terms(业务术语映射)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| term | text | NOT NULL | 如"华东区" |
| definition | text | NOT NULL | 自然语言口径,如 `regions.name = '华东'` |
| aliases | jsonb | DEFAULT '[]' | |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(kb_id, term)`。

### rules(问数全局规则)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| rule_type | text | CHECK IN ('scope','filter','style') | 范围限制 / 默认过滤 / 输出风格 |
| content | text | NOT NULL | 如"默认排除 status='cancelled' 的订单" |
| enabled | boolean | DEFAULT true | |
| created_at | timestamptz | | |

### sql_examples(few-shot 示范)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| question | text | NOT NULL | |
| sql | text | NOT NULL | |
| note | text | | 讲解这条 SQL 的要点 |
| embedding | vector(DIM) | | 按 question 嵌入,运行时检索最相似的 few-shot |
| verified | boolean | DEFAULT true | |
| created_at / updated_at | timestamptz | | |

索引:HNSW `(embedding)`。

---

## 5. 摄取骨架域(三个模块共用,S0 就要能跑)

### ingest_sources(上传的原料)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| source_type | text | CHECK IN ('file','text','db_sync') | |
| original_name | text | | 用户上传时的文件名 |
| uri | text | | FILE_STORAGE_DIR 下相对路径;text 类型时为 NULL |
| raw_text | text | NULL | source_type='text' 时直接存内容 |
| size_bytes | bigint | | |
| mime | text | | |
| uploaded_by | uuid | FK→users | |
| created_at | timestamptz | | |

### ingest_jobs(异步加工任务)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| source_id | uuid | FK→ingest_sources ON DELETE SET NULL | |
| job_type | text | NOT NULL | 'qa_extract' / 'doc_pipeline' / 'schema_sync' / 'demo_sleep'(S0 假任务) |
| status | text | CHECK IN ('queued','running','review','publishing','published','failed','cancelled') DEFAULT 'queued' | 状态机见下 |
| steps | jsonb | NOT NULL DEFAULT '[]' | 声明式步骤列表 `[{"name":"parse","title":"解析文档"}]` |
| current_step | text | NULL | |
| progress | smallint | DEFAULT 0 | 0–100 |
| step_logs | jsonb | DEFAULT '[]' | `[{"step":"parse","ts":"...","level":"info","message":"..."}]` |
| error | jsonb | NULL | `{"step":"extract","message":"...","detail":"..."}` |
| params | jsonb | DEFAULT '{}' | 任务参数(如切片大小) |
| stats | jsonb | DEFAULT '{}' | 结果统计,如 `{"extracted":42,"deduped":3}` |
| heartbeat_at | timestamptz | NULL | 执行器定期更新;启动时把「running 且心跳超时 60s」的置 failed(僵尸处理) |
| created_by | uuid | FK→users | |
| created_at / started_at / finished_at | timestamptz | | |

索引:`(status)`、`(kb_id, created_at DESC)`。
状态机:`queued → running → review →(用户点发布)publishing → published`;`running/publishing → failed`(可从失败步骤重跑);`review → cancelled`。

### staging_items(待审核的加工产物)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| job_id | uuid | FK→ingest_jobs ON DELETE CASCADE | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| item_type | text | CHECK IN ('qa_pair','chunk','table_meta','metric','term') | 决定前端用哪个渲染器 |
| payload | jsonb | NOT NULL | 结构按 item_type 定义,见 §8 |
| origin_ref | jsonb | NULL | `{"source_id":"...","page":3,"quote":"原文片段"}` 溯源定位 |
| confidence | real | NULL, CHECK (0<=confidence AND confidence<=1) | 抽取置信度,审核列表按它排序 |
| review_status | text | CHECK IN ('pending','approved','rejected','modified') DEFAULT 'pending' | modified=人工改过再通过 |
| review_note | text | | |
| reviewed_by | uuid | FK→users, NULL | |
| reviewed_at | timestamptz | NULL | |
| published | boolean | DEFAULT false | |
| published_ref | jsonb | NULL | `{"table":"exact_qa_items","id":"..."}` 发布后指向正式表 |
| conflict_with | jsonb | NULL | 冲突检测结果 `[{"item_id":"...","similarity":0.97}]` |
| created_at / updated_at | timestamptz | | |

索引:`(job_id, review_status)`、`(kb_id, item_type)`。

### publish_records(发布审计)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| job_id | uuid | FK→ingest_jobs, NOT NULL | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| item_counts | jsonb | NOT NULL | `{"approved":18,"modified":4,"rejected":2}` |
| published_by | uuid | FK→users | |
| created_at | timestamptz | | |

---

## 6. Agent 与会话域

### agents

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| name | text | NOT NULL | |
| description | text | | |
| system_prompt | text | NOT NULL | |
| router_mode | text | CHECK IN ('rule_llm','llm_only') DEFAULT 'rule_llm' | rule_llm=精准QA规则前置+LLM路由 |
| model_cfg | jsonb | DEFAULT '{}' | `{"temperature":0.3}` 等覆盖项,tier→型号映射仍在 env |
| fallback_reply | text | | 无证据时的兜底话术 |
| status | text | CHECK IN ('active','archived') DEFAULT 'active' | |
| created_at / updated_at | timestamptz | | |

### agent_kb_bindings

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| agent_id | uuid | FK→agents ON DELETE CASCADE | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| priority | int | DEFAULT 100 | 越小越优先 |
| enabled | boolean | DEFAULT true | |
| top_k | int | NULL | NULL=用该类型默认值 |
| threshold | real | NULL | 同上(精准 QA 的命中阈值等) |
| usage_desc | text | | 给路由 LLM 看的"什么问题该用这个库" |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(agent_id, kb_id)`。

### conversations

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| agent_id | uuid | FK→agents, NOT NULL | |
| user_id | uuid | FK→users, NOT NULL | |
| title | text | | 首问自动截断生成 |
| status | text | CHECK IN ('active','archived') DEFAULT 'active' | |
| last_message_at | timestamptz | | 会话列表排序用 |
| created_at / updated_at | timestamptz | | |

索引:`(user_id, last_message_at DESC)`。

### messages

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| conversation_id | uuid | FK→conversations ON DELETE CASCADE | |
| role | text | CHECK IN ('user','assistant') | |
| content | text | NOT NULL | |
| status | text | CHECK IN ('completed','failed','interrupted') DEFAULT 'completed' | |
| route_decision | jsonb | NULL | S4 路由结果快照 `{"targets":["exact_qa"],"reason":"..."}` |
| usage | jsonb | NULL | 汇总 token/成本 |
| latency_ms | int | | 端到端耗时 |
| created_at | timestamptz | | |

索引:`(conversation_id, created_at)`。

### message_citations

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| message_id | uuid | FK→messages ON DELETE CASCADE | |
| seq | int | NOT NULL | 正文中 [1][2] 的编号 |
| citation_type | text | CHECK IN ('exact_qa','chunk','sql') | |
| ref_id | uuid | NULL | 指向 exact_qa_items.id / chunks.id;sql 类型为 NULL |
| snippet | text | | 展示用摘录 |
| extra | jsonb | DEFAULT '{}' | 相似度分数 / SQL 文本 / 查询结果行数等 |

约束:UNIQUE `(message_id, seq)`。

---

## 7. 观测与评测域

### traces(S0 Step 5 就要用)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| message_id | uuid | FK→messages ON DELETE CASCADE | 一次问答的所有 stage 共享 |
| stage | text | NOT NULL | 'route' / 'retrieve_exact_qa' / 'generate' … |
| seq | int | NOT NULL | 执行顺序 |
| status | text | CHECK IN ('ok','error') DEFAULT 'ok' | 失败的 trace 也落库 |
| input / output | jsonb | | 摘要(长文本截断,原则:能看懂发生了什么即可) |
| error | text | NULL | |
| latency_ms | int | | |
| prompt_tokens / completion_tokens | int | | |
| cost_usd | numeric(10,6) | | 按型号单价估算 |
| model | text | | 实际调用的模型名 |
| created_at | timestamptz | | |

索引:`(message_id, seq)`。

### feedbacks

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| message_id | uuid | FK→messages ON DELETE CASCADE | |
| vote | text | CHECK IN ('up','down') | |
| reason | text | CHECK IN ('wrong','incomplete','irrelevant','other') NULL | down 时选填 |
| comment | text | | |
| created_by | uuid | FK→users | |
| created_at | timestamptz | | |

约束:UNIQUE `(message_id)`(单用户演示,一条消息一个反馈)。

### eval_sets / eval_cases / eval_runs / eval_results(S0 建表,S6 使用)

**eval_sets**:`id, name text NOT NULL, description text, created_at, updated_at`

**eval_cases**

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| set_id | uuid | FK→eval_sets ON DELETE CASCADE | |
| question | text | NOT NULL | |
| expected_answer | text | NULL | LLM judge 的比对基准 |
| expected_route | text | NULL | 期望命中的知识类型 |
| expected_citations | jsonb | NULL | |
| source_message_id | uuid | FK→messages ON DELETE SET NULL | "从对话加入评测集"按钮的溯源(S1 留口) |
| enabled | boolean | DEFAULT true | |
| created_at / updated_at | timestamptz | | |

**eval_runs**

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| set_id | uuid | FK→eval_sets, NOT NULL | |
| agent_id | uuid | FK→agents, NOT NULL | |
| status | text | CHECK IN ('queued','running','finished','failed') DEFAULT 'queued' | |
| config_snapshot | jsonb | | 跑分时 agent+绑定配置的快照(两次跑分可比的前提) |
| metrics | jsonb | NULL | `{"pass_rate":0.86,"avg_latency_ms":1200,...}` |
| started_at / finished_at / created_at | timestamptz | | |

**eval_results**

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| run_id | uuid | FK→eval_runs ON DELETE CASCADE | |
| case_id | uuid | FK→eval_cases, NOT NULL | |
| answer | text | | 实际回答(通过 run_chat() 产生) |
| route_actual | text | | |
| citations | jsonb | | |
| judge_verdict | text | CHECK IN ('pass','fail','unsure') NULL | |
| judge_reason | text | | |
| latency_ms | int | | |
| usage | jsonb | | |
| created_at | timestamptz | | |

约束:UNIQUE `(run_id, case_id)`。

### unanswered_pool(未命中问题池)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| agent_id | uuid | FK→agents, NOT NULL | |
| message_id | uuid | FK→messages ON DELETE SET NULL | |
| question | text | NOT NULL | |
| reason | text | CHECK IN ('no_evidence','low_confidence','route_fail') | |
| status | text | CHECK IN ('open','resolved','ignored') DEFAULT 'open' | resolved=已补充知识 |
| resolved_note | text | | |
| created_at / updated_at | timestamptz | | |

---

## 8. staging_items.payload 结构(按 item_type)

Pydantic 侧为每种 payload 建 schema,PATCH 审核修改时校验。

**qa_pair**(S1):
```json
{
  "standard_question": "HC-215 的质保期是多久?",
  "answer": "整机质保 5 年,电芯质保 10 年或 6000 次循环(先到为准)。",
  "similar_questions": ["HC215 保修几年", "储能柜质保政策"],
  "keywords": ["质保", "HC-215"]
}
```

**chunk**(S2):`{"content": "...", "heading_path": "...", "summary": "...", "hypo_questions": [...]}`

**table_meta**(S3):`{"table_name": "orders", "display_name": "订单表", "description": "...", "columns": [{"column_name": "...", "display_name": "...", "description": "..."}]}`

**metric**(S3):`{"name": "销售额", "aliases": [...], "definition_sql": "...", "unit": "元"}`

**term**(S3):`{"term": "华东区", "definition": "...", "aliases": [...]}`

---

## 9. 实体关系速览

```
users ─┬─ knowledge_bases ─┬─ exact_qa_items ── exact_qa_vectors
       │                   ├─ documents ── chunks
       │                   ├─ datasources ─┬─ table_meta ── column_meta
       │                   │               └─ relations
       │                   ├─ metrics / terms / rules / sql_examples
       │                   └─ ingest_sources ── ingest_jobs ── staging_items ── publish_records
       │
       ├─ agents ── agent_kb_bindings ──→ knowledge_bases
       └─ conversations ── messages ─┬─ message_citations
                                     ├─ traces
                                     ├─ feedbacks
                                     └─ eval_cases.source_message_id(弱引用)
eval_sets ── eval_cases ── eval_results ── eval_runs(→ agents)
unanswered_pool(→ agents, messages)
```

共 30 张表(逐项数下来是 30,早先文中写的 28 是笔误)。

**代码对应**:`server/app/models/`,一表一模型,汇总导出在 `models/__init__.py`;
初始 migration 为 `server/migrations/versions/*_initial_schema.py`。

---

## 10. 变更策略(本文档的定位与改表流程)

**定位**:机制类表(摄取骨架/会话/trace/eval/Agent)是定稿;三个知识域的业务字段是**高质量草稿**。配套纪律:**S1/S2/S3 每个阶段开工的第一件事,是带着该阶段的具体流程设计重审对应域的表,先改本文档、再动代码**——那时表还是空的,改动零成本。

**改表流程**(演示系统数据全部可由 seed/上传重建,据此选路):

| 情形 | 改法 |
| --- | --- |
| 目标域尚未使用、表为空 | 直接改初始 migration → `make db-reset`(删库重建+migrate+seed) |
| 表有测试数据但可重灌 | 改 model → `alembic revision --autogenerate` → 人工审查生成的 migration → `make migrate` |
| 只改 jsonb 内部结构(payload/meta/extra) | 只改 Pydantic schema,零 migration |
| 换 embedding 维度 / 改已发布知识结构 | 本质昂贵:重嵌入脚本 + 数据迁移,尽量在 U2 阶段避免发生 |

**铁律**:任何表结构变更,本文档先于 migration 修改;两者不一致以本文档为准并立即修正。
