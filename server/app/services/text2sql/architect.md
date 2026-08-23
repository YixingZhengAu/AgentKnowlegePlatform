# server/app/services/text2sql/architect.md

## 0. 一句话:这个域不做"自由 Text2SQL"

运行时**不让模型写 SQL**。用户问题先命中一条**人工验收过的 SQL 模板**,再由模型产出一份
结构化的"改写计划",最后由**确定性代码**把计划应用到模板的 AST 上。模型的权力只有三样:
改 WHERE 的值、减输出列、减 GROUP BY 维度。加表、加列、加条件、换算子 —— 代码层面做不到。

这条路线的代价是覆盖面(模板外的问题只能拒答),换到的是**数值可信**:每一条能跑的 SQL
都被人看过。PRD §3.5 里"智能问数:数值必须准,表达可容错"就是这个意思。

## 1. 两条链路,别混

```
【生成期】(治理台,慢、花钱、有人审)
  数据源 → introspect.py ─▶ SchemaSnapshot ─▶ semantic.py(描述生成)─▶ 语义层三张表
                                                    │
                            intents.py(意图候选)◀──┘
                                    │ 人工采纳(publisher._adopt_one → draft)
                                    ▼
                            template.py(SQL 模板 + 静态校验 + 试执行)
                                    │
                            params.py(AST 拆三区 + AI 预填 hint)
                                    │
                            questions.py(相似问法)
                                    │ 人工发布(publisher.publish_intent)
                                    ▼
                            sql_intents(published) + indexer 建索引面

【运行时】(每次提问,快、便宜、无人参与)
  用户问题 ─▶ retrieve.py(双门槛 + 空路由)
                │ 不是问数 → refused_non_data(**零 LLM**)
                ▼ 命中 top1 意图
             rewrite.make_plan(唯一一次 LLM)
                │ feasible=false → refused_out_of_template(理由 = `infeasible_reason`,逐字给用户)
                ▼
             rewrite.apply_plan(纯代码:校验 → AST 重建 SQL)
                │ violations 非空 → refused_out_of_template
                ▼
             executor.gate_and_execute(闸 + 取数)→ executed / execution_failed
  编排在 pipeline.answer(),埋点在 pipeline.trace_events()
  装配(索引/发布包/语义层/连接从库里装出来)在 runtime.py,chat 的 stage 只调它
```

**生成期的产物是运行时的输入,反过来不成立**。所以生成期的 prompt 改了要重跑评测集,
运行时的代码改了更要重跑评测集(`make smoke-s3`)。

## 2. 我要改 X,去哪

| 我要改… | 去哪 | 改完必须 |
| --- | --- | --- |
| 表/列描述的写法 | `semantic.py` 的 `_SYSTEM` + `_semantic_problems` | 重跑 `t2s_describe`,人审描述 |
| 意图分型规则 / 五个覆盖桶 | `intents.py` 的 `GEN_SYSTEM` + `BUCKETS` | 重跑 `t2s_intents` |
| 模板 SQL 的铁律或分型策略 | `template.py` 的 `GEN_RULES_COMMON` / `STRATEGY` | 重生成模板 + 全套评测集 |
| 静态校验的某一条 | `template.py` 的 `static_problems()`,**同步改 `STATIC_RULES`** | `make smoke-s3` |
| 参数区怎么拆 | `params.py` 的 `parse_params()`,**同步改 `PARSE_RULES`** | 重建所有模板包 |
| 参数 hint 的要求 | `params.py` 的 `PREFILL_SYSTEM` + `prefill_problems()` | 重跑预填,人审 hint |
| 改写器的权力边界 | `rewrite.py` 的 `REWRITE_SYSTEM`(prompt)**与** `apply_plan()`(硬约束) | 评测集,尤其越界那 4 题 |
| 应用器的裁剪/联动规则 | `rewrite.py` 的 `apply_plan()`,**同步改 `APPLY_RULES`** | `make smoke-s3` |
| 执行闸(白名单/LIMIT/超时) | `executor.py`;数值在 `.env` 的 `TEXT2SQL_*` | `make smoke-s3` |
| **SQL 长什么样**(缩进/换行/大小写) | `sqltext.py`(唯一出处);三个调用点:`template.py` 生成后落库前、`executor.py` 的 `sql_executed`、`rewrite.py::apply_plan` 的输出 | `make smoke-s3`(排版只加空白,静态校验/参数区拆解/执行闸都不该受影响) |
| 命中阈值 / 边距阈值 | `retrieve.py` 的 `HIT_THRESHOLD` / `MARGIN_THRESHOLD` | **先读 §4**,再跑 `smoke_s3_index` |
| 空路由负例面 | `non_data_faces` 表(前端可编,fixture 在 `scripts/fixtures/s3/`) | 保存即重建面 + `smoke_s3_index` |
| 相似问法 | `intent_questions` 表 + `questions.py` 的 prompt | 保存即重建面 + `smoke_s3_index` |
| 索引面的构成(哪些进索引) | `indexer.py` 的 `intent_faces()` | 重建全部面 + `smoke_s3_index` |
| 链路的终态/拒答文案 | `pipeline.py` 顶部常量;**模板外那句话来自 planner 的 `infeasible_reason`** | 评测集 + `make smoke-s3-chat`(文案有断言) |
| trace 埋哪些字段 | `pipeline.py::trace_events()`(**唯一出处**),`core/chat.py::_t2s_spans` 只照抄 | `make smoke-s3-chat` |
| 接口(增删改一条路由) | `app/api/text2sql.py` + `app/schemas/text2sql.py`,清单在 `app/api/architect.md` | `make types` + `make smoke-s3-api` |
| chat 里问数 stage 的分岔 | `core/chat.py` 的 `retrieve_text2sql` 段(拒答话术在 `pipeline.py` 顶部) | `make smoke-s3-chat` |
| 运行时装什么进来 | `runtime.py::load_runtime`(一个 kb 一个数据源是 S3 的边界) | `make smoke-s3-chat` |

## 3. 参数区:能力边界就是它

`sql_intents.params` 的三段结构(字段级定义在 DB-DESIGN §4.8)是**运行时权力的完整清单**:

| 段 | 允许 | 不允许 | 拒绝发生在 |
| --- | --- | --- | --- |
| `filters` | 改值(限 `value_type` / 枚举字典允许的范围)、禁用 | 加谓词、改算子、改列 | 计划里启用未知 filter → 应用器硬违规 |
| `outputs` | 减列 | 加列、改表达式 | 未知 param_id → 代码裁剪并记录 |
| `groupbys` | 减分组 | 加分组 | 同上 |

两个容易踩的联动,都由 `apply_plan()` 兜住,不靠模型自觉:

* 减掉一个 groupby,它的 `linked_output` 那一列必须同时减 —— 否则 MySQL 的
  `ONLY_FULL_GROUP_BY` 直接语法错;
* 分组查询里任何**非聚合**输出列,若它的表达式不在保留的分组中,也强制同减(同一个原因)。

`hint` 是给改写模型看的**取值说明书**,不是注释:日期型必须写清 `YYYY-MM-DD` 与数据窗口,
枚举型必须逐字列出每个允许值,LIKE 型必须说明是部分匹配。这三条有代码断言
(`params.prefill_problems`),AI 写漏了会被回灌重写。

## 4. 检索:为什么阈值单独已经不够(B8 逼出来的结论)

两道门槛的分工:

* `HIT_THRESHOLD = 0.45` —— top1 低于它判非问数。取值来自实测分离带的中点;
* `MARGIN_THRESHOLD = 0.03` —— top1 与 top2 咬太近时 `confident=False`,返回候选让 S4 决定
  要不要加一步 LLM 复核(**这里不实现**,也不替 S4 做决定:照跑 top1,把
  `needs_confirmation` 挂在结果上)。

**空路由(null route)是第三道,而且不可省**。B8 跑到
`What's the warranty period on the HC-300 battery cabinet?` 时,检索层**确信地**把它判给了
库存流水意图:相似度 0.5183、边距 0.2575。命中的那一面是一条含产品全名的相似问法 ——
两句话共享的是**产品名**,不是信息需求。

调阈值救不了它:0.5183 高于"应命中类"的最低分 0.4981,抬阈值必先误杀真正例。
根因恰恰是"索引面必须喂真实取值"这条纪律的反面代价(不喂,模型会编出不存在的仓库和客户)。

修法是给"以上都不是"也配一组示例面(`non_data_faces`),进**同一个向量空间**,
top1 落在这组面上就直接判非问数,**优先于绝对阈值**。实测代价为零:正例 32/32、
边界 5/5、均分 0.7523、均边距 0.1844、命中面构成全部不变;负例 13/14 → 14/14,
去掉空路由则退回 13/14。

**必须记住的副作用**:把全部负例算进来,单靠阈值已经不可分(0.5183 > 0.4981)。
`HIT_THRESHOLD` 从此只对"没被空路由拦下的问题"负责 —— 别再拿它当唯一防线。

## 5. 安全:四道关,一道都不是唯一

| # | 关 | 在哪 | 拦什么 |
| --- | --- | --- | --- |
| 1 | 模板是人工验收的 | 治理流程 | 口径错、join 错 |
| 2 | 应用器只用模板 AST 部件 + 校验过的字面量重建 SQL | `rewrite.apply_plan` | 结构上长不出模板外的表/列/条件;字符串经 sqlglot 转义,注入串只会变成普通文本值 |
| 3 | 执行闸 | `executor.gate_and_execute` | 非单条 SELECT、语义层白名单外的表列、超限 LIMIT、慢查询 |
| 4 | 数据库账号只有 SELECT | `docker/mysql/init/01-users.sql` | 一切写操作(实测 `ERROR 1142`) |

第 3 关的白名单用的是**语义层**而不是"库里有什么" —— 于是"这张表不许用于问数"这件事
在运行时也是硬约束,不只是生成期的建议。停用一张表(`table_meta.enabled=false`),
它同时从模板生成的视野和执行闸的白名单里消失。

连接串:明文只在进程内存活。落库的是 `datasources.dsn_enc`(Fernet,密钥 `SECRET_KEY`),
加解密只在 `bizdb.py`;Job 的 `params` 会落库并出接口,所以那里只放 `datasource_id`。

## 6. 从实验床迁过来时,哪些是刻意变的

Phase A/B 的实验床(当时在 `tmp/s3-dev/`,**只在开发机上,不入库,已于 2026-08-24 删除**;它评审过的
产物沉淀在 `server/scripts/fixtures/s3/`,B1–B8 的评审报告在 `documents/s3-lab-reviews/`,
逐段证据在 `documents/S3-PLAN.md`)与这里**逻辑一致、基础设施不同**。
变了的只有五处,每处都有理由:

| 变的 | 实验床 | 这里 | 为什么不算"改核心" |
| --- | --- | --- | --- |
| LLM 调用 | 同步 openai SDK + 自己的重试 | `app/providers`(`llm.py` 适配) | provider 的 tier 映射 / headroom / effort / JSON 自愈与实验床逐项对齐,行为相同,多了 usage 记账 |
| Embedding | 同步 + 本地文件缓存 | `app/providers` + pgvector | 入库前 L2 归一化,于是本地点积 == pgvector 余弦;`smoke_s3_index` 强制对数(1.66e-07) |
| 语义层 | `out/semantic_layer.json` | `load_layer()` 从三张表装同形字典 | 形状逐字一致;多带一个 `samples` 键,值是同一次同步抓的同一批采样 |
| 模板采样值 | 回读 `out/schema_snapshot.json` | 从语义层的 `samples` 取 | 同一批值,少一个数据源 |
| 索引 | 内存 list + 文件缓存 | `intent_vectors` 表 | 判定逻辑(`_score_intents` / `_decide`)是逐字复制的,有断言守着 |

C4/C5 又附加了三处,都是**只增不改**(评测集分数未变,仍是 20/20):

| 加的 | 在哪 | 为什么不算"改核心" |
| --- | --- | --- |
| `llm.collect_usage()` | `llm.py` | contextvar 收集桶。要记账但**不能改六个评审过模块的调用行**,所以账从旁路走,调用形状一个字没动 |
| `gate_and_execute(..., preview=)` 与结果里的 `elapsed_ms` | `executor.py` | preview 只决定回带几行样本(治理台 Run 面板要多几行才看得出数对不对);elapsed_ms 让改写与取数的耗时能分开记。**闸的判定与 `sql_executed` 都不受影响** |
| `trace_events()` 里两个 stage 的耗时拆分 | `pipeline.py` | 原来 `execute_sql` 的 latency 是 `None`(改写与执行连着跑,只有合计值)。现在减出取数那一段,两者相加仍等于合计 —— 这是 C3 计划里明确留给 C5 的一件事 |

**证据**:`scripts/smoke_s3_e2e.py` 把 B8 冻结的 20 题在这条路径上重跑,
`--check` 与 `--all` 都是 20/20,硬闸门 7/7,`execution_failed` 0,踩线题仍然只有 E05
—— 与 B 阶段逐项一致。这份对照是"只换基础设施"这句话的唯一证据,别让它失效。

## 7. 三个 Job 与它们的重跑成本

| Job | 步骤 | 花钱吗 | 终态 | 什么时候重跑 |
| --- | --- | --- | --- | --- |
| `t2s_sync_schema` | introspect / persist | 零 | published | 库结构变了就跑,随时可跑 |
| `t2s_describe` | generate / save | 每张启用的表一次 gpt-5 | published | 换了描述的写法、或新启用了表 |
| `t2s_intents` | generate / judge / stage | 一次 gpt-5 + 一次 gpt-5-mini | **review** | 想再要一批意图(已有的会喂回 prompt 要求避重) |

`judge` 那一步是生成完自己盲判一遍(只给 brief,不给 type 与前缀,判"要不要 GROUP BY")。
**不一致不拦**,只写进候选的 `confidence` 让它排在前面 —— 判官本身也会错,
它的价值是"提醒人看这一条",不是"替人否决"。
