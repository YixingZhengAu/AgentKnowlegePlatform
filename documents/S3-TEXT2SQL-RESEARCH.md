# S3 Text2SQL 工业界调研与 B4 方案建议(2026-08-23)

> 调研目的:B4(SQL 模板生成)动工前,确认工业界稳定、高准确率的 text2sql 做法,
> 对照本项目已定架构,给出 B4 的具体输入输出整理方式。
> 两路调研:①头部产品做法(Snowflake / Databricks / Vanna / dbt / Looker / Uber / LinkedIn);
> ②基准与技术的实测增益(Spider 2.0 / BIRD / 各消融研究)。来源清单见文末。

---

## 一、调研核心结论(带数字)

### 1.1 裸 schema 自由生成在真实企业库上不及格

| 场景 | 准确率 | 来源 |
|---|---|---|
| Spider 1.0(学术小库,已刷穿) | ~91% | Spider 榜单 |
| BIRD(较真实) | 73–81% | CHASE-SQL / XiYan-SQL 等 |
| **Spider 2.0(真实企业库,千列级)** | **同一模型从 91% 掉到 17–21%**(GPT-4o 仅 10%) | Spider 2.0 论文(ICLR 2025) |
| GPT-4o 单发裸 schema,Snowflake 真实 BI 评测集 | **51%** | Snowflake 工程博客 |
| Databricks Genie 案例:裸基线 | 53–54% | codecentric / Syren 案例 |

**最致命的失败模式是"静默错答"**:SQL 能跑、结果像样、数字是错的
(如营收统计忘排除 cancelled 订单,虚高 15–30% 无人察觉)。消融研究显示
"能跑但结果错"约为"跑不起来"的 2 倍;失败案例里 **过滤条件错占 ~54.6%**,
时间/范围口径错另占 ~14.4%。—— 语法错误是小问题,**口径错才是大问题**。

### 1.2 技术手段按实测增益排序

以 Intel/MIT 消融研究(GPT-4.1,真实 25 表库,43.3% → 90.0%)为主轴,多源互证:

| 排名 | 手段 | 实测增益 | 备注 |
|---|---|---|---|
| 1 | **语义层(列描述/枚举含义/业务口径)** | +13~26pp;Snowflake 57→78%;dbt 基准 84~90→98~100% | 所有研究中最大单一杠杆 |
| 2 | **已验证 question→SQL 对(few-shot/检索)** | 单用 +10pp;**与语义层叠加 43→83%** | Vanna 明言这是准确率首要决定因素 |
| 3 | 多候选 + 选优(self-consistency/judge) | +5~9pp | 运行时自由生成才需要 |
| 4 | **执行反馈自修复(报错回灌,≤2 轮)** | +3~7pp,执行失败归零 | 主要修"跑不起来",不修"口径错" |
| 5 | Schema linking(表列检索剪枝) | 千列库必需;**小库反而有害**(漏列风险) | 7 表库应全量喂 |

### 1.3 工业界收敛点:没有一家生产系统做纯自由生成

所有头部产品对业务用户的架构都收敛到同一形态:

**可靠性阶梯**:裸 schema(~50%)→ +元数据描述(~70–80%)→ +语义层口径/关系(~85–95%)→ **verified query 命中(≈100%,可标记"已验证")**

- **Snowflake Cortex Analyst**(90%+):人工维护 semantic model YAML(表/维度/指标/同义词/命名过滤器/**verified_queries**)+ 多 Agent(问题分类拒答→检索 verified query→生成→编译器纠错→judge 选优)
- **Databricks Genie trusted assets**:人工认证的**参数化示例 SQL,命中后用户只能改参数值**,答案带 "trusted" 标记;案例阶梯 53% → 80%(补元数据)→ 100%(补口径+示例 SQL)
- **dbt Semantic Layer**(最强约束形态):**LLM 根本不写 SQL**,只输出结构化请求(指标+维度+过滤),由 MetricFlow 确定性编译成 SQL;基准 84~90% → 98~100%
- **Vanna.ai**:RAG on(DDL+文档+已验证 SQL 对),检索不到相似对时退化到 ~50%
- **LinkedIn SQL Bot**(诚实数字):内部基准仅 53% 正确,但用户满意度 95% —— 自由生成靠"人工迭代兜底"才可用,一次命中率上不去

**共识**:高频/口径敏感问题走认证模板(确定性),长尾探索才走受约束生成;
模糊问题**反问澄清而非硬猜**;评测基准做成产品功能(内置题集回归)。

---

## 二、对照:本项目架构 = 工业界收敛点的组合

结论先行:**本项目 S3 的三层漏斗与头部产品的收敛架构逐层同构,方向不用改。**
这也是面试可讲的点——我们不是"又一个 NL2SQL demo",而是 Cortex Analyst 的
verified-query 路线 + dbt 的结构化输出路线的自研轻量组合。

| 本项目 | 工业界对应物 | 佐证 |
|---|---|---|
| B2 语义层(表/列描述、枚举含义、AI 生成+人审) | Snowflake semantic model / Genie 元数据 | 最大杠杆,+13~26pp |
| B3–B4 意图+模板(人审定稿,保存即发布) | **Genie trusted assets / Snowflake verified_queries** | 命中即 ≈100% 档 |
| B5 参数区(filters/outputs/groupbys + hint) | Genie "只允许改参数值" 的参数化认证查询 | 同形态 |
| B6 改写计划(LLM 出结构化 JSON,不出 SQL)+ 确定性应用器 | **dbt "LLM 输出结构化请求,确定性编译"** | 最强约束形态 |
| B6 应用器 ⊆ 规则硬裁剪 | AST 级白名单(工业界:不用 regex,用 AST) | 生产 guardrail 标配 |
| B7 意图检索 | verified query 相似检索 | Snowflake/Vanna 同款 |
| B8 评测集(改写问法+边界+拒答) | Genie benchmark / Snowflake 150 题内部集 | "自己的评测集是唯一算数的数字" |
| 只读账号 biz_reader + B6 执行闸(SELECT-only/LIMIT/超时) | 只读角色+AST 校验+行数上限+超时 | 生产 table stakes |

调研映射到本项目的**准确率预期**:模板命中场景(我们的全部 runtime 场景)对标
Genie trusted assets / Snowflake VQR 命中档,B8 定的 ≥90% 目标现实可达;
真正的风险点不在 SQL 语法,而在**模板口径**(B4 人审重点)与**改写忠实度**(B6)。

---

## 三、B4 具体方案建议

### 3.1 定位修正认知

B4 是**离线一次性生成 + 人工评审定稿**,不是运行时生成。因此:
- 不需要多候选 self-consistency(+5~9pp 是运行时自由生成的收益;这里人就是 selector);
- 不需要 schema 检索(意图已人工圈定 tables,直接喂该子集全量语义层);
- **人审的重点按失败分布聚焦:join 路径、聚合口径、WHERE 默认条件**(对应 54.6% 的过滤错 + 口径错)。
- 评审要看得见 LLM 的口径决策 → 输出必须带结构化的"设计说明",不能只给一条 SQL。

### 3.2 输入整理(喂给生成 prompt 的东西)

全部来自已冻结产物,组装规则确定性:

```
输入 = {
  business_context: BUSINESS_CONTEXT,          # B2 已有常量(澳洲光伏支架公司、销售侧、AUD)
  intent: {id, type, one_liner, brief},        # adopted_intents.json 原文;brief 即口径依据
  schema_subset: {                             # semantic_layer.json 按 intent.tables 裁剪
    tables: [{name, description,
              columns: [{name, type, key, nullable, display_name, description, enum_values}]}],
    relations: [...]                           # 仅两端都在 tables 内的关系(join 唯一依据)
  }
}
```

要点:
- **brief 就是口径的唯一出处**(如 i07 的 "excluding orders with status cancelled")——prompt 明确要求 SQL 必须落实 brief 里的每一条口径,并在设计说明里逐条对应;
- 分型双策略(计划已定,调研佐证):query 版强调可参数化 WHERE + ORDER BY + LIMIT;stats 版强调 GROUP BY 维度结构与聚合口径,排名类必须 ORDER BY 聚合值 + LIMIT;
- prompt 内置 **每型一个手写规范样例**(few-shot 第二大杠杆,离线一次成本为零):一个 query 样例、一个 stats 样例,示范别名风格、字面量默认值、口径落实方式。

### 3.3 输出整理(json_schema 结构化输出)

```
输出 = {
  sql: "...",                                  # 单条 MySQL SELECT,可直接运行
  design: {                                    # 结构化设计说明 —— 人审抓手,对抗静默错答
    join_path: "orders o JOIN customers c ON o.customer_id = c.id" | null,
    measures: [{expr: "SUM(o.total_amount)", meaning: "..."}] | null,   # stats 才有
    group_by_dims: ["..."] | null,
    default_filters: [{column, operator, value, why}],   # 每个 WHERE 条件的业务理由
    caliber_notes: ["Revenue excludes cancelled orders per intent brief", ...]  # 口径逐条声明
  }
}
```

- `sql` 走后置管道(sqlglot 解析 → 静态校验 → 真库试执行 → 报错自修 ≤2 轮,计划已定);
- `design` 不进管道、不入模板,只进评审报告 —— 让"LLM 以为的口径"显式化,人审对着 brief 逐条勾。

### 3.4 SQL 风格铁律(写进 prompt + 静态校验双保险)

1. 单条 SELECT,只允许 intent.tables 内的表(校验层硬断言);
2. **每个 WHERE 条件必须是 `列 操作符 字面量` 的简单形态**(=、>、>=、BETWEEN、IN、LIKE),不许把条件埋进子查询/HAVING(除非聚合值过滤必须 HAVING)——这是 B5 sqlglot 拆参数的前提;
3. **时间默认值写绝对日期字面量**(如 `>= '2025-08-23'`,按今天回推),不用 CURDATE() 算术 —— 与 B6 "时间值必须给绝对区间" 的规则统一,B5 才能把它拆成可改写的 filter 参数。模板默认值会过期没关系:运行时 B6 每问都按用户话重算区间,hint 里写清默认窗口含义;
4. 输出列全部带可读英文别名(取自语义层 display_name 风格,如 `AS monthly_revenue`);
5. query 型:必有 ORDER BY(通常时间倒序)+ LIMIT;必不含 GROUP BY。stats 型:必含 GROUP BY;排名类 ORDER BY 聚合值 + LIMIT;
6. 试执行记得 pymysql 坑:`cur.execute(sql, params or None)`,含 `DATE_FORMAT('%Y-%m')` 的 SQL 不能带非 None args。

### 3.5 模板定稿文件与评审报告

`out/templates/{intent_id}.json`(人审认可/手改后定稿,B5 的冻结输入):

```
{intent_id, type, one_liner, sql, design,
 trial: {row_count, columns, rows_preview(≤10), repair_rounds},
 generated_at, human_edited: true|false, edit_note?}
```

`out/B4-REVIEW.md`(沿用 B3 的反漂移模式,机制披露从代码常量渲染):
- 每意图一节:brief 原文 → 最终 SQL → design 逐条(口径对照 brief)→ 执行结果前 10 行 → 自修轨迹;
- 机制披露:分型 system prompt 全文、输入组装规则、json_schema、静态校验清单、自修回灌格式;
- 人审清单(每条模板三问):join 路径对不对 / 口径落实了 brief 每一条吗 / WHERE 默认条件合理吗。

### 3.6 明确不采纳的技术及理由

| 技术 | 不采纳理由 |
|---|---|
| 多候选 + judge 选优 | 离线 7 条模板,人审就是 selector;运行时我们不自由生成,无此需求 |
| Schema 检索/列剪枝 | 7 表小库,调研明确"小库剪枝有害";意图 tables 已人工圈定 |
| Token 级 constrained decoding(PICARD 类) | 工业界少用;我们用"模板 + 结构化改写计划 + 确定性应用器"替代,约束更强且可解释 |
| LangChain/Vanna 等现成框架 | 与 CLAUDE.md 编排纪律一致:自研轻量,面试可解释性优先 |

---

## 四、对后续阶段的三条补充建议(调研新增,非 B4 范围)

1. **B6 加空结果/异常量级 sanity flag**:改写后 SQL 执行结果为空或行数异常时,不直接答数,标注"该条件下无数据/请确认条件"——调研中静默错答的廉价缓解;
2. **答案侧口径复述**(Phase C 聊天集成时):回答旁边用一句英文复述实际生效的过滤与口径("Monthly revenue, cancelled orders excluded, Jan–Aug 2026")——Snowflake/Genie 的 "trusted + 可见口径" 同款,让错误假设可被用户看见;
3. **B8 金标集就是唯一算数的数字**:BIRD 官方判卷与人类专家一致率仅 62%,外部榜单数字仅供方向;我们 ≥20 改写问法 + 边界/拒答 100% 的自建集设计正确,坚持每次改动全量回归。

---

## 五、来源清单(精选)

- Snowflake Cortex Analyst 准确率与架构:snowflake.com/en/blog/engineering/cortex-analyst-text-to-sql-accuracy-bi(90%+ vs GPT-4o 51%)、…/cortex-analyst-behind-the-scenes(多 Agent 流水线)、semantic view YAML spec(docs.snowflake.com)
- Databricks Genie:docs.databricks.com/en/genie/trusted-assets(参数化认证查询)、genie/best-practices;codecentric / Syren 案例(53%→80%→100% 阶梯)
- dbt 语义层基准(2026,开源可复现):docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026(84~90%→98~100%);github.com/dbt-labs/dbt-llm-sl-bench
- Spider 2.0(ICLR 2025):arxiv.org/pdf/2411.07763(91%→17% 的企业现实差距);榜单 spider2-sql.github.io
- Intel/MIT 消融(VLDB 2026 NOVAS):43.3%→90.0% 配方(注释+样例+执行校验),各组件独立增益
- CHASE-SQL(ICLR 2025)/ XiYan-SQL / Distillery("Death of Schema Linking",arxiv.org/abs/2408.07702)
- Vanna 训练建议:vanna.ai/docs/training-advice(verified pair 是首要决定因素)
- Uber QueryGPT / LinkedIn SQL Bot(53% 基准 vs 95% 满意度)/ Pinterest Querybook:各家工程博客与 ZenML LLMOps DB
- 失败分布:过滤错 54.6%(arxiv 企业 grounding 基准);模板覆盖幂律(~13% 模板型覆盖 ~70% 真实查询,arxiv 2603.25568)
