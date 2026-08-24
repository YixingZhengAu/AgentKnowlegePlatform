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

## 4. 智能问数域(语义层 + 已验证意图)

> **本节在 S3 开工时按实测重写(2026-08-23)**,替换 v0.1 的草稿。改动的依据不是审美,
> 而是 Phase B 的实测结论(逐条证据见 `documents/S3-PLAN.md` 的 B1–B8 证据块):
>
> 1. **不做"自由 Text2SQL"**。运行时不让模型现写 SQL,而是**命中一条人工验收过的
>    SQL 模板**,再在模板的参数区里做受约束改写(只准换值、减列、减分组,不准加谓词、
>    不准换表)。所以这里的一等公民是 **`sql_intents`(意图 = 模板 + 参数区)**。
> 2. **`metrics` / `terms` / `rules` / `sql_examples` 四张表废弃**(见下方"§4.9 废弃说明")。
>    它们服务的是"自由生成 + few-shot"路线;模板路线里指标口径已经**焊死在模板 SQL 里**,
>    再放一份可漂移的口径定义,等于给同一件事留两个出处。
> 3. **演示业务库改用 MySQL 8.4**(独立容器,端口 3307),所以 `datasources.db_type`
>    放开到 `mysql`。理由:面试演示要展示"接入客户已有的库",而客户库以 MySQL 为多;
>    同时它逼着 introspection 走 `information_schema` + distinct 采样这条真实路径。
> 4. 检索层是**语义路由**:意图的相似问法与"以上都不是"的负例面进**同一个向量空间**,
>    所以索引面表 `intent_vectors` 的 `intent_id` 可空(空 = 空路由伪意图)。

### datasources

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| name | text | NOT NULL | |
| db_type | text | CHECK IN ('mysql','postgres') DEFAULT 'mysql' | 演示库是 MySQL 8.4;PG 留着是因为 introspection 走的是 `information_schema`,换库只换方言 |
| dsn_enc | text | NOT NULL | 连接串,Fernet 对称加密,密钥来自 env `SECRET_KEY`。**明文永不落库、永不出接口** |
| readonly_confirmed | boolean | DEFAULT false | 运维确认该账号只读;false 时执行闸直接拒(不是提示,是拒) |
| status | text | CHECK IN ('active','disabled') DEFAULT 'active' | |
| last_synced_at | timestamptz | | 最近一次 schema 同步完成时间(前端显示"元数据是否过期") |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(kb_id, name)`。

### table_meta

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| datasource_id | uuid | FK→datasources ON DELETE CASCADE | |
| schema_name | text | NOT NULL | MySQL 下就是 database 名(`demo_biz`);PG 下是 schema |
| table_name | text | NOT NULL | |
| display_name | text | | 业务名(英文,平台面向澳洲用户) |
| description | text | | 给 LLM 的表用途说明,**AI 预填 + 人工确认**(B2) |
| physical_comment | text | | 库里原本的表注释,同步时抓取。是治理素材,不是成品 —— 演示库刻意只有一部分表列有注释 |
| enabled | boolean | DEFAULT true | 治理开关:是否纳入问数范围 |
| row_count_estimate | bigint | | 同步时统计 |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(datasource_id, schema_name, table_name)`。

### column_meta

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| table_meta_id | uuid | FK→table_meta ON DELETE CASCADE | |
| column_name | text | NOT NULL | |
| ordinal | int | | 库里的列序,前端表格按它排(按字母排会让 id/主键跑到中间) |
| data_type | text | | 同步时抓取,如 `varchar(128)` / `decimal(12,2)` |
| is_nullable | boolean | DEFAULT true | 同步时抓取 |
| key_flag | text | | `PRI` / `UNI` / `MUL`,同步时抓取;join 提示与主键识别都要它 |
| physical_comment | text | | 库里原本的列注释,同步时抓取 |
| display_name | text | | 业务名,AI 预填 + 人工确认 |
| description | text | | 给 LLM 的列说明,AI 预填 + 人工确认 |
| is_sensitive | boolean | DEFAULT false | true 时模板生成与改写都禁止 SELECT 此列 |
| distinct_count | int | | 同步时统计,判"像不像枚举"用 |
| is_enum_like | boolean | DEFAULT false | 低基数且类型合适 → 视为枚举维度 |
| enum_values | jsonb | NULL | **结构变了**:`[{"value":"NSW","meaning":"New South Wales."}]`。v0.1 是裸 string[],但改写阶段真正需要的是"值→含义",模型才敢把"新南威尔士的单"映射到 `NSW` |
| sample_values | jsonb | NULL | 同步时采样 ≤5 个值(截断到 80 字符),帮模型理解格式 |
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
| source | text | CHECK IN ('foreign_key','heuristic','human') DEFAULT 'foreign_key' | **来源必须留痕**:演示库刻意有两处"该有 FK 但没建"的逻辑关联(`orders.sales_rep_id`、`inventory.product_id`),它们是命名启发式猜出来的,可信度与真 FK 不同,人审时要能一眼分开 |
| description | text | | |

约束:UNIQUE `(datasource_id, from_table, from_column, to_table, to_column)`。

### sql_intents(★ 本域的核心表:意图 = 已验收的 SQL 模板 + 参数区)

一条 `sql_intent` 就是"一类能被准确回答的数据问题"。它不是 few-shot 素材,是**运行时唯一
会被执行的 SQL 的来源** —— 运行时只在它的参数区内做受约束改写,不重新生成 SQL。

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| datasource_id | uuid | FK→datasources ON DELETE CASCADE | 模板绑死在某个数据源上(SQL 方言与表名都是它的) |
| code | text | NOT NULL | 人可见的稳定短标识(`i01`…),报告/trace/评测集都引它;换 uuid 会让所有人审材料失去可读性 |
| intent_type | text | CHECK IN ('query','stats') NOT NULL | 列明细 / 出聚合。**分型决定模板生成策略与参数区形状**,不是标签 |
| bucket | text | | 生成期的归类(`multi_table_query` / `time_stats` …),用于覆盖面自查 |
| one_liner | text | NOT NULL | 一句话摘要(带 `Query:`/`Stats:` 治理前缀)。**进索引前会剥掉前缀** —— 前缀是内部治理标签,用户问句里绝不会出现 |
| brief | text | NOT NULL | 说明书体详述(给模板生成与人审看)。**刻意不进检索索引**:B7 消融实测它对"问句 vs 问句"匹配零增益,却制造 3 条意图间自洽性冲突 |
| tables | jsonb | DEFAULT '[]' | string[],涉及的物理表 |
| sql | text | | 已验收的模板 SQL(带默认参数值,可直接执行)。**存的是多行排版后的文本** —— 它是要给人读、给人编辑、给人验收的治理资产,一行几百字符没法审;排版只加空白不动语义,唯一出处 `services/text2sql/sqltext.py` |
| params | jsonb | DEFAULT '{}' | 参数区三段结构,见 §4.8 |
| status | text | CHECK IN ('draft','published','disabled') DEFAULT 'draft' | published 才进检索索引 |
| prefill_rounds | int | DEFAULT 0 | 参数区 AI 预填用了几轮(含回灌自修),质量留痕 |
| human_edited | boolean | DEFAULT false | 人是否改过 SQL 或参数区 |
| source_staging_id | uuid | FK→staging_items ON DELETE SET NULL | 溯源到候选(与 S1 同一条纪律:正式表不复制 origin_ref) |
| published_at | timestamptz | | |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(kb_id, code)`。索引:`(datasource_id)`、`(kb_id, status)`。

### intent_questions(相似问法:可编辑子资产)

概念与 S1 精准问答的"相似问题"完全一致 —— 检索时比的是**问句 vs 问句**,而不是问句 vs 说明文。
AI 生成 ~8 条,人可增删改;**保存即重建该意图的索引面**。

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| intent_id | uuid | FK→sql_intents ON DELETE CASCADE | |
| question_text | text | NOT NULL | 英文,一句一条 |
| origin | text | CHECK IN ('ai','human') DEFAULT 'ai' | 人改过的那条要能看出来 |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(intent_id, question_text)`。

> **本表不存向量** —— 向量在 `intent_vectors`。分开的理由和 S1 一样:问法集合一变就
> **全删重建**该意图的索引面,不做增量 diff;把向量挂在可编辑资产行上,就得处理
> "改了一条、删了一条、又加回来"的组合,是自找麻烦。

### non_data_faces(空路由负例面:"以上都不是"的示例)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| face_text | text | NOT NULL | 一句"明显不是问数"的问题(产品规格/质保/操作手册/故障码/流程政策/闲聊) |
| origin | text | CHECK IN ('ai','human') DEFAULT 'human' | |
| enabled | boolean | DEFAULT true | |
| created_at / updated_at | timestamptz | | |

约束:UNIQUE `(kb_id, face_text)`。

> **这张表为什么必须存在**(B8 实测逼出来的,不是设计洁癖):
> `What's the warranty period on the HC-300 battery cabinet?` 会**确信地**命中库存流水意图
> (相似度 0.5183、边距 0.2575),因为它和一条含产品全名的相似问法**共享产品名**。
> 调阈值救不了 —— 0.5183 高于"应命中类"的最低分 0.4981,抬阈值必先误杀真正例。
> 区分它靠的不是分数高低,而是**索引里有没有一个更像的负例**。
> 实测:加上它,非问数负例 13/14 → 14/14,而正例 32/32、均分、均边距、命中面构成**全不变**。

### intent_vectors(索引面:一面一行)

运行时检索的唯一数据来源。一次问答只读这一张表(按 kb 取全部面 → 每意图取其所有面的
**max** 相似度 → 双门槛判定)。

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | 检索的过滤维度 |
| intent_id | uuid | FK→sql_intents ON DELETE CASCADE, **NULL 允许** | NULL = 空路由伪意图(`__non_data__`)。**这一列可空是本域最需要解释的设计**:空路由要能和真意图在同一次比较里竞争,才可能"比所有真意图都更像",所以它必须住在同一张索引表里 |
| face_kind | text | CHECK IN ('summary','question','non_data') NOT NULL | 评审报告要能回答"哪一类面在真正干活" |
| face_text | text | NOT NULL | 被嵌入的原文(剥过治理前缀) |
| embedding | vector(DIM) | NOT NULL | |
| created_at | timestamptz | | |

约束:CHECK `(face_kind = 'non_data') = (intent_id IS NULL)`(两边必须同时成立,防出现"挂在真意图上的负例面"这种脏数据)。
索引:HNSW `(embedding)` + `(kb_id)`。

> **维护规则**:意图发布 / 相似问法保存 / 负例面保存 → **全删重建**对应的面
> (意图的:该 intent_id 的全部行;负例的:该 kb 下 `intent_id IS NULL` 的全部行)。
> 意图下线(`status='disabled'`)= 删它的面,正式行留着可追溯。

### §4.8 `sql_intents.params` 的三段结构

参数区由**代码从模板 SQL 的 AST 解析出骨架**(不是 LLM 想象出来的),再由 AI 给每个参数
预填业务名与 `hint`(人可改)。运行时改写只允许在这三段之内动。

```json
{
  "filters": [{
    "param_id": "f_movement_date",
    "kind": "filter",
    "source": "stock_movements.movement_date",
    "operator": "BETWEEN",
    "value_type": "date",          // date | enum | number | string | id
    "value_shape": "range",        // scalar | range | list
    "default_value": ["2025-08-23", "2026-08-23"],
    "predicate_sql": "sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'",
    "business_name": "Movement date range",
    "hint": "给改写模型看的映射说明:什么样的用户说法该改成什么值,默认值是什么,什么情况下才允许禁用"
  }],
  "outputs":  [{ "param_id": "o_...", "kind": "output",  "expr": "...", "alias": "outbound_units", "source": "...", "business_name": "...", "hint": "..." }],
  "groupbys": [{ "param_id": "g_...", "kind": "groupby", "expr": "...", "source": "...", "linked_output": "o_...", "business_name": "...", "hint": "..." }]
}
```

三段各自允许的运行时动作(**这就是"能力边界"的定义,超出的一律拒答**):

| 段 | 允许 | 不允许 |
| --- | --- | --- |
| `filters` | 改值(在 `value_type`/枚举字典允许的范围内)、禁用 | 加新谓词、改算子、改列 |
| `outputs` | 减列 | 加列、改表达式 |
| `groupbys` | 减分组(连带删掉 `linked_output` 那一列) | 加分组维度 |

> `linked_output` 存在的原因:SQL 里减掉一个 GROUP BY 维度却把对应的 SELECT 列留着,
> 在 MySQL 严格模式下直接是语法错。这条链接让"减分组"变成一个原子动作。

### §4.9 废弃说明:metrics / terms / rules / sql_examples

四张表在 S3 开工时**物理删除**(它们从建库起就是空的,没有任何代码写过)。删而不是留空的理由:
schema 是给后来的人读的文档,留四张永不写入的表,等于留四条会误导人的线索。

| 废弃的表 | 它服务的路线 | 在模板路线里被谁替代 |
| --- | --- | --- |
| `metrics`(指标口径) | 自由生成时告诉模型"营收怎么算" | **焊死在 `sql_intents.sql` 里**,并经人工验收。口径只有一个出处,不会漂移 |
| `terms`(业务术语) | 自由生成时做同义词映射 | `intent_questions`(用户怎么问 → 命中哪个意图)+ `column_meta.enum_values` 的 value→meaning |
| `rules`(全局口径规则) | 拼进 prompt 的软约束 | 模板 SQL 里的固化谓词 + 参数区 `hint`(硬约束),软约束改成硬约束 |
| `sql_examples`(few-shot) | 提示模型照着写 | 模板本身就是"被验证过的答案",不再需要"像什么样"的示范 |

> 如果日后要做"自由 Text2SQL"兜底(模板全都不命中时现写 SQL),这四张表要连同它们的
> 治理界面一起重新引入 —— 那是一条独立的、准确率完全不同的链路,不是本表的扩展。

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

**S1 的两点收窄**(实现见 `server/app/services/exact_qa/`):

1. **逐条采纳即发布**,没有批量发布动作,于是 `publishing` 这个中间态在 S1 的
   `qa_extract` 上不出现:`review` 表示"采纳进行中",全部候选裁决完毕(没有 pending)
   自动置 `published`,它只作终态统计,漏斗数字记在 `publish_records.item_counts`。
   批量入口 `POST /api/jobs/{id}/publish` 仍然可用(走同一个 publisher),两条路不冲突。
2. **不产出待审内容的 Job 直接进终态**:`qa_parse` 跑完就是 `published`
   (等人校对这件事由 `documents.parse_status` + 推导态表达,不占用 job 状态)。

### staging_items(待审核的加工产物)

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | uuid | PK | |
| job_id | uuid | FK→ingest_jobs ON DELETE CASCADE | |
| kb_id | uuid | FK→knowledge_bases, NOT NULL | |
| item_type | text | CHECK IN ('qa_pair','chunk','table_meta','metric','term') | 决定前端用哪个渲染器 |
| payload | jsonb | NOT NULL | 结构按 item_type 定义,见 §8 |
| origin_ref | jsonb | NULL | 溯源定位。**S1 定稿形状**(`schemas/exact_qa.py::OriginRef`):`{"document_id":"...","page_idx":3,"quote":"原文片段","bbox":[x0,y0,x1,y1]}` —— `page_idx` **0 起**(与 MinerU 一致,前端显示 +1),`bbox` 每轴归一化到 0–1000(原点左上、页面尺寸无关),**可空**(quote 跨块时给不出唯一框)。早期示例写的 `{source_id,page,quote}` 已按此更正 |
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

### S1 落地补充:exact_qa_items / exact_qa_vectors 的两条使用约定

- **正式表不存 origin_ref**:出处经 `source_staging_id` 回 `staging_items.origin_ref` 取
  (复制一份就多一处会不同步的数据)。
- **下线 = `status='disabled'` + 删该 item 的全部向量行**,正式行不物理删
  (它可能被 `message_citations.ref_id` 引用过,删了历史消息的引用会悬空)。
- 索引面 = 标准问 + 每条相似问各一行;问题集合一变就**全删重建**该 item 的向量行,
  不做增量 diff。检索用 `1 - cosine_distance`(HNSW 建在 `vector_cosine_ops` 上)。

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
> S1 实现说明:`origin_ref`(原文出处)与 `confidence`(抽取置信度)**不在 payload 里** ——
> 它们各有专属列。payload 就是采纳后原样写进 `exact_qa_items` 的那四个字段
> (`QaCandidate.as_payload()`),这样发布时不用做字段裁剪。
> 抽取阶段的硬约束:答案非空 + quote 必须能在校对文本里逐字定位到,不满足的候选直接丢弃。

**chunk**(S2):`{"content": "...", "heading_path": "...", "summary": "...", "hypo_questions": [...]}`

**sql_intent**(S3,意图候选 —— AI 提的"这类问题值得做成模板吗"等人采纳):
```json
{
  "code": "i16", "intent_type": "stats", "bucket": "time_stats",
  "one_liner": "Stats: Monthly outbound units trend by warehouse",
  "brief": "Aggregates outbound movements into a monthly trend ...",
  "tables": ["stock_movements"]
}
```

> **S3 只有这一种候选进审核台**,v0.1 的 `table_meta` / `metric` / `term` 三种 payload 一起废弃。
> 另外两样 S3 产物刻意不走 staging,各有自己的界面:
>
> | 产物 | 为什么不进泛型审核台 | 它的审核界面 |
> | --- | --- | --- |
> | 表/列 description | 审它的时候必须**同屏看到采样值与枚举字典**,否则没法判断描述对不对;而审核台是一列卡片,给不了这个上下文 | Schema 治理页(就地编辑 + 单字段 AI + 表级批量 AI) |
> | SQL 模板与参数区 | 审的是"**这条 SQL 能不能跑出对的数**",要能改 SQL 再 Run 一遍看结果 | 意图详情页(生成 → Run → 改 → 发布) |
>
> 于是 S3 的采纳与发布是**两件事**:采纳(审核台)= "这类问题值得做成模板",
> 意图落成 `status='draft'`;发布(意图详情页)= "这条模板我验收了",才 `published` 并建索引面。

---

## 9. 实体关系速览

```
users ─┬─ knowledge_bases ─┬─ exact_qa_items ── exact_qa_vectors
       │                   ├─ documents ── chunks
       │                   ├─ datasources ─┬─ table_meta ── column_meta
       │                   │               └─ relations
       │                   ├─ sql_intents ─┬─ intent_questions
       │                   │               └─ intent_vectors ←── non_data_faces
       │                   │                  (intent_id IS NULL 的面 = 空路由)
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

共 30 张表。S3 开工时**净数不变**:新增 4 张(`sql_intents` / `intent_questions` / `non_data_faces` / `intent_vectors`),删除 4 张(§4.9 的 `metrics` / `terms` / `rules` / `sql_examples`)。

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
