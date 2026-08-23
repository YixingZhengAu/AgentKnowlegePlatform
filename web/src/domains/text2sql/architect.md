# web/src/domains/text2sql/ · architect

## 页面与路由

```
/ingest/text2sql                                        DatasourcesPage(D1:接库 + 同步 + 治理进度)
/ingest/text2sql/datasources/:datasourceId/schema        SchemaPage(D2:语义层编辑台)
/ingest/text2sql/intents                                 IntentsPage(D3:意图台账 + 生成 + 负例面)
/ingest/text2sql/intents/:intentId                       IntentDetailPage(D4:一条模板的验收台)
/jobs/:jobId/review                                      共享审核台 + 本域渲染器(D3)
```

chat 里的 `sql` 引用由本域的 `SqlCitation.tsx` 画(D5),
登记点是 `module.ts` 的 `citations`(与审核渲染器同一套 manifest 模式)。

共享路由表只给每个域一个 `/ingest/<域>/*` 空间(`src/App.tsx`),域内二级页在
`IngestPage.tsx` 的 `<Routes>` 里摆 —— **本域加页面不需要碰任何共享文件**。

## 治理者旅程与页面的对应

| 旅程步骤 | 落在哪 | 出口动作 |
| --- | --- | --- |
| ① 接一个只读库 | `DatasourcesPage` 的 `NewDatasourceCard` | Test connection → Save(`POST /datasources`) |
| ② 确认只读 | 列表那一行的 Confirm | `PATCH /datasources/{id}` `{readonly_confirmed:true}` |
| ③ 同步物理事实 | 列表那一行的 Sync / Re-sync | `POST /datasources/{id}/sync` → `<JobProgress>` |
| ④ 写语义层 | `SchemaPage` 左右两栏 | 按表 `PUT /tables/{id}`;AI 单点 / 批量两个入口 |
| ⑤ 提意图候选 | `IntentsPage` 的 `GenerateCard`(选表 + 条数) | `POST /datasources/{id}/intents` → `<JobProgress>` → 审核台 |
| ⑥ 采纳成 draft | `/jobs/{id}/review`(本域渲染器 + 动作层) | 逐条 Adopt as draft → 那颗批量按钮真正调 publisher |
| ⑦ 手工补一条 | `IntentsPage` 的 `NewIntentCard` | `POST /intents`(建出来也是 draft) |
| ⑧ 维护空路由 | `IntentsPage` 的 `NonDataFacesCard` | `PUT /non-data-faces`,**保存即重建向量** |
| ⑨ 验收一条模板 | `IntentDetailPage` 的五张卡 | 生成模板 → Run → 参数区 → 问法 → Publish |
| (清场) | 列表那一行的垃圾桶 | `DELETE /datasources/{id}`,**两步确认**;挂着意图的后端 409 |

## D1 的四个实现要点

1. **测连有两个接口,表单用不落库的那个**(`POST /datasources/test`)。所以"填错口令"
   不会先在库里留下一个必然失败的数据源。改任何一个连接要素都会把上一次的测连结果作废
   (`set()` 里清 `tested`)—— 否则会出现"绿勾还在,但要素已经换了"。
2. **连不上是业务结果**:接口 200 + `ok=false`,前端只读 `ok`/`error`,不解析错误码。
   走进 `catch` 的才是真异常(网络断了 / 请求本身错了)。
3. **Read-only confirmed 是闸不是提示**:没确认时后端 409 掉同步 / AI 描述 / 试跑,
   所以列表里那一格显示的是**一个必须点掉的动作**(Confirm),不是一句说明文字。
4. **有 Job 在跑才轮询列表**:治理进度那几个数字跟着 Job 一格格变;进度卡关掉就停 ——
   演示时后台不该一直有请求在滚。

## D2 的五个实现要点

1. **按表保存,不逐格保存**。草稿是 `drafts: Record<tableId, TableDraft>`,**只存被改过的
   字段**;保存时也只发这些,没碰过的字段后端一个字不写(`PUT /tables/{id}` 的语义:
   `None` = 不写)。切表不丢草稿,左侧列表上有未保存标记,多张表各自保存。
2. **左侧的启用开关立即落库**(唯一的例外)。它不是文字编辑,是"这张表算不算数"的闸;
   在列表里放一个要等 Save 才生效的开关,读起来会像已经生效了。
3. **单列的 AI 按钮也整表生成**。评审过的 prompt 是表级的(靠同表其他列、join 与采样值
   一起判断一列是什么),所以按钮打的是同一个 `POST /tables/{id}/describe`,**只回填那一格**;
   这一条在按钮的 title 里对用户明说。
4. **AI 只给建议,不落库**(单点入口)。单点同步返回 → 填进草稿 → 人看过再 Save;
   批量(每张启用的表一次 gpt-5)走 Job **直接写库**,进度用共享 `<JobProgress>`。
   `Fill gaps` / `Rewrite all` 对两个入口同时生效。

   ★ **fill 保住的是库里的 DDL 注释,不是人在这一页打的字**(出处
   `services/text2sql/semantic.py` 头部:"已有 DDL 注释的列逐字保留")。D2 自测实测过:
   fill 模式的批量 Job 把手写的表描述和列描述都换成了模型/注释的版本。所以页面上那条
   提示按模式给两句不同的话,**没有**写成"fill 不会动你写的东西" —— 那是假承诺。
   要不要给"人改过的描述"加一道保护(列级 human_edited),是需求方的产品决定,
   记在 `documents/S3-PLAN.md` 的 D2 证据里,不在 D 阶段私自改 B2 评审过的模块。
5. **采样值与枚举字典必须看得见**。判断一句描述对不对,靠的是这一列真实长什么样;
   枚举列展示「值 → 含义」,因为改写阶段真正需要的是这个,不是裸 string。

## D3 的三个实现要点

1. **候选审核不自己造列表**。"筛选 / 编辑 / 批量采纳 / 键盘流"对三类知识是同一套流程,
   所以本域只提供 `renderers.tsx`(卡片 + 编辑器)与 `actions.ts`(动作层),
   人从生成进度卡上的 `Review items` 进泛型审核台。
   ★ **采纳 ≠ 发布**:本域保留 S0 的泛型语义(标 approved → 批量发布),
   而"发布"这一步在后端调的是本域 publisher —— 它建的是 **draft 意图**,不进检索。
   按钮文案因此改成 `Adopt as draft`。
   ★ `confidence` 在本域不是置信度:0.5 = 生成 Job 的盲判与声明的 type 不符
   (`ingest.py::step_judge`)。审核台默认按 confidence 升序,那几条自己排最前,
   卡片上把它写成人话("check type"),不摆一个看不懂的 0.5。
2. **追加生成是安全动作**。生成 prompt 会把本 kb 已有意图的摘要喂回去要求避重
   (`ingest.py::step_generate` 的 `avoid`),所以"再生成一批"可以反复点,不是重置。
   选表是刻意留的:只喂人想要的几张表,生成质量比全库一把梭高。
3. **空路由负例面摆在意图列表页**。它是 **kb 级**资产(不属于任何单个意图),
   而本域里 kb 级的页面就是这一页;Agent 设置页属于 shared 层,域开发者不该往里塞本域资产。
   面板里那段话不是提示而是它存在的理由:非问数问题靠"索引里有更像的负例"拦下,
   靠阈值拦不住(B8 实测),清空这一组等于关掉空路由。

## D4 的六个实现要点

1. **一张卡片一次保存**。四块内容打的是四个不同的后端动作(`PATCH /intents/{id}` 的
   信息与 SQL、`PATCH` 的 params、`PUT …/questions`),做成一个"全保存"就等于把
   "四个请求里第二个失败了"这种半成品状态摆给用户。所以每张卡自己管草稿、自己有 Save
   与 Revert,标题栏挂 `unsaved`。
2. **生成模板是整条替换,这句话必须在按钮旁边**。`POST …/template` 走完 B4+B5 全链路
   (生成 → 9 条静态校验 → 真库试执行 → 报错自修 ≤2 轮 → AST 拆参数 → AI 预填),
   返回时 SQL 与参数区已经落库 —— 人手写过的 hint 也会没。
3. **生成器的设计说明是评审材料,不是提示文案**。`DesignPanel` 把 join 路径 / 度量口径 /
   分组维度 / **写死的过滤及其理由** / 口径备注分行摆出来。写死的过滤最该被看见:
   它不在参数区里,就意味着运行时改不动它。
   ★ 这一轮把后端契约也改了:`TemplateResult.design` 原本写成 `str`,而
   `services/text2sql/template.py` 的结构化输出返回的是对象,任何一次生成都 500。
   新增 `TemplateDesign` / `DesignMeasure` / `DesignFilter`(`schemas/text2sql.py`),
   形状跟着 template.py 的 json_schema(那边 measures/group_by_dims 允许 null,所以逐项可空)。
4. **Run 打的是运行时那道执行闸**,不是另一条通路。所以"Run 过了"含义明确:这条 SQL
   在运行时不会因为闸(非单条 SELECT / 表列不在白名单 / LIMIT / 超时)而失败。
   被闸拒是 200 + `ok=false`,面板里原样显示闸说的那句话(自测实测:
   `gate: column o.bogus_id not in whitelist`),**不是异常、不弹 error toast**。
   生成链路里那一次试执行共用这个面板,但标成 `trial run from the generator`
   且不显示 `sql_executed` —— 那条 SQL 就在上面的编辑器里,重复摆一遍反而像被闸改写过。
5. **参数区重解析是纯代码、零 LLM**,按 `param_id` 保住人写过的业务名与 hint;
   它读的是**库里那条 SQL**,所以编辑器有未保存改动时按钮变灰(否则会拿旧 SQL
   解析出一份对不上的参数区)。自测实测:把两个日期边界改成一个,参数 id 从
   `f_order_date_ge` 变 `f_order_date`,于是"5 参数 · 保住 3 条注释" —— 变了的那个就该丢注释。
6. **发布按钮变灰的原因一律来自后端 `publish_blockers`**,前端一个字不自己编
   (那套校验只有一处出处:`services/text2sql/publisher.py`)。
   相似问法那张卡的 `origin` 只说明"这条问法从哪来的":`PUT …/questions` 是整组替换、
   不做逐条 diff(向量挂在意图上),所以走过这个编辑框的一律记 `human` —— 卡片底部那句话
   照这个事实写,不写成"N 条来自模型"那种会立刻变成假话的说法。

## 两处这一轮修掉的东西(签字同意后才动)

1. `t2s_intents` 的 `step_stage` 之前没写 `ctx.scratch["stats"]`,于是共享 `<JobProgress>`
   在审核入口那块显示「0 items are waiting for review.」而底下明明有三条。
   本域后端一行修好(`services/text2sql/ingest.py`)。
2. 共享 `<JobProgress>` 对 `review|published` 无条件渲染审核入口,导致
   `t2s_sync_schema` / `t2s_describe`(不产出条目、终态就是 published)跑完出现
   「0 items published.」+ 一个点进去是空审核台的按钮。按 D1/D2 阶段提出的那个一条件改法
   落地:`reviewCount(job) > 0` 才渲染(`components/JobProgress.tsx`)。

## D5 的四个实现要点

1. **数据全在 `citation.extra` 里,前端不再发一次请求**。出处
   `services/text2sql/runtime.py::citations`:结果集(cols/rows/rowcount/flags)、
   意图摘要与分数都随引用落库成 jsonb。理由有两层:那条 SQL 再跑一次未必是同一份数,
   而引用是要**留档**的 —— 点开历史消息看到的表,就是当时那张表(自测实测:
   刷新后从 `message_citations` 读回来,表格、行数、SQL 与高亮全在)。
2. **结果表格默认摊开,最终 SQL 折叠**。结论那句话(`pipeline._summarise`,确定性拼的、
   没过生成模型 —— 所以敢标 Verified)是从表里算出来的,所以先让人看见表;
   SQL 是"这个数怎么来的"的证据,点开就能复制到 MySQL 里跑(自测实测:
   粘出来 354 字符,与执行过的原文逐字相同)。高亮共用 D4 编辑器那份配色
   (`sqlTokens.ts`),**只加 span,不动一个字符**,所以复制到的仍是原文。
3. **踩线过的命中要说出来**。`extra.needs_confirmation`(= 是问数问题但 top1 与 top2
   的边距不够)之前一路带到前端却没人显示,于是踩线命中与稳命中长得一模一样。
   现在引用里多一句"下一名分数几乎一样,确认这是你要问的那件事"(自测实测:E05
   `Monthly outbound units for Melbourne and Brisbane…` 命中 i16 0.737,提示出现)。
4. **trace 面板不用为本域改一行**:五要素(意图分数 / 模板 id / 计划 / 最终 SQL /
   行数+耗时)是 `pipeline.trace_events()` 摊出来的三个 span,`core/chat.py::_t2s_spans`
   照抄。自测实测面板上四段:`retrieve_exact_qa` → `retrieve_text2sql`(零 LLM)
   → `rewrite_sql`(唯一一次模型调用,账记在它头上)→ `execute_sql`,三段耗时之和等于总耗时。

## D5 自测抓出来的一个用户可见缺陷(已修)

模板外拒答显示给用户的那句话,取的是 planner `notes` 的第一条 —— 而那条通常是
"日期解析成了 2025-08-23 到 2026-08-23"这种记账。实测:问"按利润率排前十的客户",
页面上答的是一句讲日期的话,和问题毫无关系。

修法是给理由一个**自己的字段**:`rewrite.py` 的计划 schema 加 `infeasible_reason`
(必填,prompt 里写明"feasible=false 时写一句直接给用户看的话"),
`pipeline.answer` 与 `smoke_s3_e2e.py` 的重放路径都只认这个字段,取不到才落固定文案。
`smoke_s3_chat.py` 加了断言把这个坑钉死(拒答文案必须逐字等于 `infeasible_reason`)。
改过 prompt/schema 就要回评测集:`--all` 真调 20 题仍 20/20、硬闸门 7/7。
⚠ `eval_plans.json` 是 B8 冻结的评审资产,没有这个新字段,所以 `--check` 重放时
拒答会落到固定文案 —— 断言不看文案,成绩不受影响,要看真实理由跑 `--all`。

## 我要改 X 去哪

| 改什么 | 去哪 |
| --- | --- |
| 新建数据源的表单字段 | `DatasourcesPage.tsx` 的 `NewDatasourceCard` |
| 测连结果怎么显示 | `DatasourcesPage.tsx` 的 `TestResult` |
| 列表一行显示什么 / 有哪些动作 | `DatasourcesPage.tsx` 的表格主体 |
| 表清单一行显示什么 | `SchemaPage.tsx` 左栏的 `<li>` |
| 字段表格有哪些列 | `SchemaPage.tsx` 的 `TablePanel` |
| 采样值 / 枚举怎么展示 | `SchemaPage.tsx` 的 `ColumnValues` |
| 保存请求发什么 | `SchemaPage.tsx` 的 `save()` |
| AI 建议怎么回填 | `SchemaPage.tsx` 的 `describe()` |
| 开关的样子 | `Toggle.tsx` |
| 意图台账一行显示什么 | `IntentsPage.tsx` 的表格主体 |
| 生成用哪些表 / 几条 | `IntentsPage.tsx` 的 `GenerateCard` |
| 手工新建的字段 | `IntentsPage.tsx` 的 `NewIntentCard` |
| 空路由负例面 | `IntentsPage.tsx` 的 `NonDataFacesCard` |
| 候选卡片 / 编辑器长什么样 | `renderers.tsx` |
| 采纳 / 驳回到底做了什么 | `actions.ts` |
| PUT 请求 / 报错取文案 | `http.ts` |
| 详情页的卡片顺序 / 外壳 | `IntentDetailPage.tsx` 的 `CardShell` 与顶层组件 |
| 发布 / 下线那一条 | `IntentDetailPage.tsx` 的 `PublishBar` |
| SQL 生成 / Run / 重解析 | `IntentDetailPage.tsx` 的 `TemplateCard` |
| Run 结果 / 报错怎么显示 | `IntentDetailPage.tsx` 的 `RunPanel` |
| 生成器设计说明摆哪些字段 | `IntentDetailPage.tsx` 的 `DesignPanel` |
| 一个参数的折叠卡 | `IntentDetailPage.tsx` 的 `ParamRow` |
| 相似问法区 | `IntentDetailPage.tsx` 的 `QuestionsCard` |
| SQL 高亮的词法与配色 | `sqlTokens.ts`(编辑器与引用卡共用) |
| chat 里问数引用怎么显示 | `SqlCitation.tsx` |
| 结果表格 / 行数 / 闸的 flags | `SqlCitation.tsx` 表格那一段 |
| 最终 SQL 的展开与复制 | `SqlCitation.tsx` 底部两个按钮 |
| 踩线命中的提示语 | `SqlCitation.tsx` 的 `thin` 分支 |
| 拒答给用户看的那句话 | `services/text2sql/rewrite.py` 的 `infeasible_reason` + `pipeline.answer` |
