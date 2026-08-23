# server/app/services/text2sql/

**职责**:智能问数(Text-to-SQL)知识域的全部后端逻辑 —— 语义层治理、意图与 SQL 模板生成、
运行时受约束改写、执行闸、检索。
准确率相关的逻辑先在一个开发机上的实验床里逐段实测调优并经人工评审(B1–B8,证据见
`documents/S3-PLAN.md`,评审过的产物在 `server/scripts/fixtures/s3/`),
**这里是原样平移的落点**;prompt 与判定逻辑不在这里改,要改先回评测集验证。

| 文件 | 说明 |
| --- | --- |
| `bizdb.py` | 客户库连接层:DSN Fernet 加解密 + 只读连接 + 同步查询(**params 必须传 None,不能传 ()**) |
| `llm.py` | 调用适配:把 Phase B 的 `complete(messages, tier=, json_schema=)` 形状接到 `app/providers` |
| `introspect.py` | B1:MySQL introspection → SchemaSnapshot(冻结格式,后续所有 prompt 的唯一供料) |
| `semantic.py` | B2 描述生成 + snapshot 落库(**只覆盖物理事实,不碰治理字段**)+ 语义层装配 `load_layer()` |
| `intents.py` | B3:意图候选生成 + 两个 light-tier 盲判(GROUP BY 分型 / 追加批判重) |
| `template.py` | ★ B4:SQL 模板生成 + 9 条确定性静态校验 + 真库试执行 + 报错回灌自修 ≤2 轮 |
| `params.py` | B5:AST 拆三区参数骨架(纯代码)+ AI 预填 business_name/hint + 校验回灌 ≤2 轮 |
| `rewrite.py` | ★ B6:改写计划 prompt + **确定性应用器**(校验 → sqlglot AST 重建 SQL)+ 全链路 `rewrite()`;计划里的 `infeasible_reason` 是拒答文案的唯一出处 |
| `sqltext.py` | 「SQL 长什么样」的唯一出处:AST → 多行排版(`pretty=True`)。落库前与展示前都过它,**只加空白不动语义**,解析失败原样返回 |
| `executor.py` | 执行闸:单条 SELECT / 表列白名单 / 强制 LIMIT / 读超时。**最后一道关,不是唯一一道** |
| `questions.py` | B7:相似问法生成(必须喂真实取值表)+ 文本层跨意图冲突过滤 |
| `retrieve.py` | ★ B7:双门槛判定 + **空路由**(null route)+ 索引装载 + 留一法审计 |
| `indexer.py` | 索引面维护:摘要 + 每条问法各一行,空路由面 `intent_id IS NULL`;一变就全删重建 |
| `pipeline.py` | ★ B8:端到端编排(检索 → 计划 → 应用 → 执行)+ `trace_events()`。**刻意无 I/O** |
| `runtime.py` | 运行时装配:Agent 绑定 → 索引/发布包/语义层/连接 → 调 pipeline;`core/chat.py` 只调这里 |
| `publisher.py` | 采纳(候选 → draft 意图,`@register_publisher("sql_intent")`)+ 发布/下线(建/删索引面) |
| `ingest.py` | 三个 Job:`t2s_sync_schema` / `t2s_describe` / `t2s_intents`(**只有它写 `stats.staged`** —— 审核台入口那块数字就是它) |
| `__init__.py` | 只做一件事:import `publisher` 触发 publisher 注册 |

**四个必须记住的设计点**(展开在 `architect.md`):

1. **运行时不生成 SQL**,只在已验收模板的参数区内改值 / 减列 / 减分组,越界一律拒答。
2. **空路由是必需项**:非问数问题靠"索引里有更像的负例"拦下,靠阈值拦不住(B8 实测)。
3. **四个终态分开记**:`refused_non_data`(零 LLM)/ `refused_out_of_template` / `executed` /
   `execution_failed`(**永远算 bug**,不是业务边界)。
4. **采纳 ≠ 发布**:采纳只表示"这类问题值得做成模板"(draft),发布才建索引面。

**纪律**:不 import 兄弟域;只向上依赖 `app/core` / `app/models` / `app/schemas` / `app/providers`。

**接口与问答链路**:`app/api/text2sql.py`(21 条路径,清单在 `app/api/architect.md`)、
`app/core/chat.py` 的 `retrieve_text2sql` stage(只调 `runtime.py`,不掺本域知识)。

**冒烟**(`make smoke-s3` 跑前三条,全部零 LLM):
`scripts/verify_bizdb.py`(业务库 27 项数据断言)、`scripts/smoke_s3_index.py`
(**pgvector 余弦 vs 手算点积对数** + 留一法审计 + 空路由回归)、
`scripts/smoke_s3_e2e.py`(B8 的 20 题评测集,`--check` 零 LLM / `--all` 真调 / `--question` 单问);
HTTP 层 `scripts/smoke_s3_api.sh`(`make smoke-s3-api`,27 步、含错误路径、**不留痕**)、
chat 链路 `scripts/smoke_s3_chat.py`(`make smoke-s3-chat`,三问 + trace 五要素 + SSE 协议)。
演示知识的灌入:`scripts/seed_s3_demo.py`(`make seed-s3`),资产在 `scripts/fixtures/s3/`。

详见 `architect.md`。
