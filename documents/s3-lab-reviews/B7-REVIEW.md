# B7 评审:意图检索(相似问法索引 + 双门槛判定)

生成时间 2026-08-23T19:41:14 · embedding `text-embedding-3-small` / 1536 维 · 索引面 75 条 / 7 个意图

## 人审三问

1. **相似问法质量**(§1):每条问法是不是真的只能由该意图回答?有没有把问题问宽、或者写得像另一个意图?真实用户会问而这里没覆盖的问法,现在补最省事 —— 直接改 `out/intent_questions/{id}.json` 的 `questions` 数组,再跑 `--check`。
2. **阈值与边距**(§3):看三类分数分布的分离带,认不认可冻结的 `HIT_THRESHOLD=0.45` / `MARGIN_THRESHOLD=0.03`?
3. **职责边界**(§4 边界例):"问数域但模板外"的问题(Perth 仓库 / 毛利 / 销售代表)在这里**命中最近意图**、由 B6 拒答 —— 这个分工认不认可?
4. **空路由负例面**(§2.2,B8 实测后补的):`out/non_data_faces.json` 里那组"以上都不是"的示例,覆盖面够不够、有没有写得像真问数问题?同样人可编辑。

**定稿动作**:改问法 JSON(可增删改)→ `--check` 复验 → 认可后本 stage 关闸,问法与阈值随 Phase C 原样迁移落库。

## 结论速览

| 项 | 结果 | 通过线 |
| --- | --- | --- |
| 正例 top-1 命中(B6 真人题 11/11 + 生成改述 21/21) | **32/32 = 100%** | ≥ 90% |
| 非问数负例全部低于阈值 | **14/14** | 100% |
| 边界例(模板外问数)命中最近意图 | **5/5** | 100% |
| 索引自洽性审计(留一法) | **61/63** 条面检回自己(可改的问法面冲突 **0** 条) | 问法面 0 冲突 |
| 阈值**单独**能否分开正负例 | **不能**(重叠 [0.5183, 0.4981],见 §3) | — |
| 空路由 + 阈值**联合**判对负例 | **14/14** | 100% |
| 空路由拦下的负例 | 13/14 条(其余靠阈值拦);误伤应命中题 **0** 条 | 误伤 0 |

## §1 相似问法资产(本 stage 的主要人审对象)

概念同 S1 精准问答的"相似问题":索引里比的是**问句 vs 问句**,而不是问句 vs 说明文。每个意图的索引面 = 摘要面(剥掉 Query:/Stats: 前缀的 one-liner)+ 下列问法,各自一行向量;该意图得分 = 所有面的 **max**(命中任何一种问法都算命中这个意图)。意图简述(brief)**不入索引**,理由见 §2.1 消融。

生成时把兄弟意图的摘要一并喂给模型,要求"不能同时像兄弟意图"(源头防冲突);生成后再过两道正交的关:文本层 Jaccard 冲突(本节 §1.1)、向量层留一法审计(§2)。

#### i01 — Query: Recent orders for a specific customer

> Returns detailed orders for a chosen customer, including order number, date, status, and order total. Users typically vary the customer (by name or ID), a date range, and statuses to include or exclude (e.g., exclude cancelled). Results can be sorted by most recent or highest value.

索引摘要面(已剥前缀):`Recent orders for a specific customer`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i01.json`) |
| --- | --- |
| 1 | Show me the most recent orders for Summit Manufacturing Pty Ltd over the last six months, excluding cancelled, with totals. |
| 2 | List all orders for Boomerang Textiles Pty Ltd placed since 2026-01-01, with status and order total, newest first. |
| 3 | Pacific Dairy Co-op Pty Ltd orders from 2025-07-01 to 2026-08-23, only show paid or completed. |
| 4 | Can I get the recent order history for Coastal Aggregates Pty Ltd this quarter and hide any that were cancelled? |
| 5 | Summit Logistics Pty Ltd orders year to date, include order number, date, status, and total, sorted by highest value. |
| 6 | Summit Manufacturing Pty Ltd recent orders last 90 days exclude cancelled. |
| 7 | Recent orders for Boomerang Manufacturing Pty Ltd in the past 30 days, all statuses, most recent first. |
| 8 | Customer: Pacific Dairy Co-op Pty Ltd — show orders from July 2026, exclude cancelled and pending. |

#### i02 — Query: Line items for an order number

> Lists all product lines on a given order: product SKU/name, quantity, unit sell price, and line amount in AUD. Users provide an order number and may also filter to active products only for validation.

索引摘要面(已剥前缀):`Line items for an order number`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i02.json`) |
| --- | --- |
| 1 | Can you list all the line items on order SO-2026-01281, showing SKU or name, quantity, unit sell price, and the line total in AUD? |
| 2 | Show me the product lines for SO-2026-01270, active products only. |
| 3 | What products are on SO-2026-01255 and how many units of each at what unit price? |
| 4 | Order SO-2026-01281 item breakdown: SKU/name, qty, unit price, line amount. |
| 5 | Line items for sales order SO-2026-01270 with quantities and line totals (exclude inactive). |
| 6 | Please itemise SO-2026-01255 with SKU, quantity, unit sell price and extended amount. |
| 7 | Give me all products on order SO-2026-01281 with their quantities and prices per unit. |
| 8 | SO-2026-01270 line items, active only — qty, unit price, line value. |

#### i07 — Stats: Monthly revenue trend (excluding cancelled)

> Aggregates total booked revenue per calendar month based on order date, summing order totals in AUD and excluding orders with status cancelled. Users vary the date range and may filter by status to focus on completed/paid bookings.

索引摘要面(已剥前缀):`Monthly revenue trend (excluding cancelled)`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i07.json`) |
| --- | --- |
| 1 | Show monthly sales revenue in AUD for the last 12 months, excluding cancelled. |
| 2 | Monthly booked revenue by order date since 2025, paid and completed only. |
| 3 | Can you chart total order revenue by month from 2024-09 through today? |
| 4 | Revenue by month (AUD) for last quarter, completed status only. |
| 5 | Monthly sales totals in AUD year to date, exclude cancelled orders. |
| 6 | Trend of booked revenue per calendar month for 2025. |
| 7 | Revenue by month since Jan 2026, paid orders only. |
| 8 | Monthly revenue trend AUD, 2025-01 to 2025-12, exclude cancelled |

#### i09 — Stats: Top 10 customers by revenue (last 12 months)

> Ranks customers by total booked revenue in AUD over a chosen period (commonly the last 12 months), excluding cancelled orders. Aggregation is the sum of order totals per customer; ties can be broken by most recent order date.

索引摘要面(已剥前缀):`Top 10 customers by revenue (last 12 months)`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i09.json`) |
| --- | --- |
| 1 | Top 10 customers by revenue last 12 months |
| 2 | Can you list our top 10 customers by booked revenue for the last year, excluding cancelled orders? |
| 3 | Show the top 10 customers by total order value year to date. |
| 4 | Who were our 10 highest-revenue customers over the past 12 months? |
| 5 | Top 10 customers by sales revenue since Sep 2024. |
| 6 | Rank customers by total revenue for the last 365 days — top 10 only. |
| 7 | Give me the top 10 revenue customers for 2026 YTD, ignoring cancelled. |
| 8 | Top 10 customers by AUD revenue in the past year |

#### i15 — Query: Stock movement history for a product at a warehouse

> Shows the chronological ledger of movements for a chosen product at one warehouse over a date range, including movement date, type (inbound/outbound/adjustment), quantity, running balance after, and source reference. Users typically set the product, warehouse, and time window to investigate receipts, deliveries, or stocktakes. Useful for tracing discrepancies or confirming dispatches.

索引摘要面(已剥前缀):`Stock movement history for a product at a warehouse`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i15.json`) |
| --- | --- |
| 1 | Can you show me the stock movement ledger for HC-300 at the Sydney warehouse for June 2026, with running balances? |
| 2 | I need the in/out/adjustment history and running balance for PowerCab HC-100 Battery Cabinet 100kWh in Brisbane since March 2026. |
| 3 | Give me the chronological stock movements for HC-215 at Melbourne for the last 90 days, including source references. |
| 4 | HC-215 Sydney stock movements since 2026-07-01 |
| 5 | Show all movements and balances for HC-50 in Sydney for 2026 year to date. |
| 6 | I want the detailed movement log (receipts, dispatches, adjustments) for PowerCab HC-1000 Battery Cabinet 1MWh at Melbourne for July 2026. |
| 7 | Pull the movement ledger for HC-500 at Brisbane for 2026-08-01 to 2026-08-07, with running balances. |
| 8 | Trace every stock movement for PowerCab HC-300 Battery Cabinet 300kWh at Sydney from 2026-05-01 to 2026-08-23, with references. |

#### i16 — Stats: Monthly outbound units trend by warehouse

> Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses.

索引摘要面(已剥前缀):`Monthly outbound units trend by warehouse`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i16.json`) |
| --- | --- |
| 1 | Can you show monthly outbound units by warehouse for the last 12 months? |
| 2 | Month-by-month units shipped out per warehouse, covering Brisbane, Melbourne and Sydney. |
| 3 | Sydney outbound volume by month |
| 4 | Monthly outbound dispatch trend by warehouse from 2024-09-01 to today. |
| 5 | Compare outbound units per month by warehouse, Melbourne only. |
| 6 | Trend of units sent out each month by warehouse across all warehouses. |
| 7 | For Brisbane and Sydney, show monthly outbound movements by month since Jan 2026. |
| 8 | Outbound shipments per month by warehouse, FY26 to date. |

#### i18 — Stats: Top products by outbound units (last 90 days)

> Ranks products by shipment volume over a recent period. Groups by product and sums quantity where movement_type is outbound within the chosen window (e.g., last 90 days), then orders descending to return the top N products; this reflects units shipped to customers. Users vary the lookback window and optionally limit to certain warehouses.

索引摘要面(已剥前缀):`Top products by outbound units (last 90 days)`

| # | 相似问法(可直接改这个文件:`out/intent_questions/i18.json`) |
| --- | --- |
| 1 | Can you show top products by units shipped in the last 90 days? |
| 2 | Top 5 products by outbound units from Sydney over the past three months. |
| 3 | Which products rank highest by units shipped in the last 60 days, counting Brisbane and Melbourne only? |
| 4 | Top products by outbound volume last 90 days. |
| 5 | Which SKUs led by units shipped since 1 May 2026? |
| 6 | Rank products by quantity shipped to customers in the last quarter. |
| 7 | Top 10 products by units shipped year to date from the Brisbane warehouse. |
| 8 | Give me the products with the highest outbound units in the past month. |

### §1.1 生成后被代码丢弃的问法

本轮无丢弃(生成时已带兄弟意图约束,源头没产生冲突问法)。

## §2 索引自洽性审计(留一法)

每条索引面**把自己从索引里排除**后再检索一次,必须检回自己所属的意图。检回别的意图 = 这句话会把用户主动拉去错的模板,是索引里最有害的数据。

冲突分两类,处理方式不同:**问法面**是本 stage 的资产、能改;**摘要面**是 B3/B5 已发布的意图 one-liner,B7 不动它 —— 一条 one-liner 单独看不够区分,恰恰就是相似问法要补的短板(它自己的问法面把它的分撑住了,所以不影响命中)。

✅ **问法面 0 冲突**(56 条问法面全部检回自己)。

#### 本轮据审计改写的问法(2 条,人可否决)

- **i16**
  - 改前:`Month-by-month units shipped out, split by Brisbane, Melbourne and Sydney.`
  - 改后:`Month-by-month units shipped out per warehouse, covering Brisbane, Melbourne and Sydney.`
  - 原因:leave-one-out audit: this face retrieved the sibling intent (0.7633) instead of its own; the distinguishing word (per warehouse / rank products) was missing
- **i18**
  - 改前:`Which products have shipped the most units from Brisbane and Melbourne in the last 60 days?`
  - 改后:`Which products rank highest by units shipped in the last 60 days, counting Brisbane and Melbourne only?`
  - 原因:leave-one-out audit: this face retrieved the sibling intent (0.7633) instead of its own; the distinguishing word (per warehouse / rank products) was missing

#### 摘要面冲突(2 条,信息项,不处理)

| 意图 | one-liner | 单独看更像 | 对方分 | 自己分 |
| --- | --- | --- | --- | --- |
| i01 | Recent orders for a specific customer | i02 | 0.5824 | 0.5601 |
| i15 | Stock movement history for a product at a warehouse | i16 | 0.6013 | 0.5152 |

> 这两条正是"只索引意图描述会出事"的实证:光看 one-liner,"某客户的近期订单" 更像 "某订单的明细行"、"某产品在某仓库的出入库流水" 更像 "按仓库的月度出库量"。加了问法面之后,这两个意图在真实问题上一题没错。

### §2.2 空路由(非问数负例面)—— B8 端到端评测倒逼出来的补丁

**这一节是 B7 定稿后被 B8 推翻重做的部分,请重点看。**

B8 跑到 `What's the warranty period on the HC-300 battery cabinet?` 时,检索层**确信地判错**:命中 i15(某产品在某仓库的出入库流水),分数 0.5183、边距 0.2575。命中的那一面是 `I need the in/out/adjustment history and running balance for PowerCab HC-100 Battery Cabinet 100kWh in Brisbane since March 2026.` —— 两句话共享的是**产品名**,不是信息需求。

调阈值救不了它:0.5183 高于应命中类的最低分(0.4981),抬阈值必然先误杀真正例。根因是 §5 的取值表纪律 —— 索引面刻意带真实产品名,于是"问这个产品的属性"和"查这个产品的数据"在词面上高度重叠。区分它们靠的不是分数高低,而是**索引里有没有一个更像它的负例**。

所以给"以上都不是"也配一组示例面(12 条,伪意图 `__non_data__`):top1 落在这组面上 → 直接判非问数,**优先于绝对阈值**(见 §5 判定规则)。这是语义路由的标准做法,零 LLM 成本,复用同一套 max-over-faces 机制。

防作弊:这些面**不得与评测集里的负例(§4.3)或 B8 的 E18–E20 逐字重合**,只覆盖同样的类别、措辞另写 —— 否则就是拿答案考自己。

| # | 负例面(`out/non_data_faces.json`,人可编辑) |
| --- | --- |
| 1 | Does the HC series come with an extended warranty option? |
| 2 | What is the operating temperature range of the INV-250K inverter? |
| 3 | Which certifications does the PowerCab cabinet hold for the Australian market? |
| 4 | How do I wire the Monitoring Gateway G2 to a third-party meter? |
| 5 | What annual maintenance does the HVAC cooling module need? |
| 6 | Explain the difference between the EMS Lite and EMS Pro licences. |
| 7 | What does a flashing red LED on the inverter mean? |
| 8 | Who do I escalate a customer complaint to? |
| 9 | What is our returns process for a faulty accessory? |
| 10 | Can you write a follow-up email to a distributor? |
| 11 | What are the public holidays in Queensland this year? |
| 12 | Good morning — how are you today? |

实测:拦下 13/14 条非问数负例,误伤应命中题 0 条(0 条 —— 加它没有代价)。

### §2.1 消融实验:索引面构成(表由 `ablation()` 现算,非手抄)

只看 top-1 命中率看不出差别(7 个意图这个规模,各变体在评测集上都满分),所以看**均分 / 均边距 / 谁在当命中面**。只用 B6 那 11 道真人题 —— 生成的改述是从摘要+简述派生的,拿它比会偏袒这两类面。

| 索引面构成 | 面数 | 真人题命中 | 均分 | 均边距 | 负例判对 | 负例最高真实意图分 | 命中面类型 | 留一法冲突 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 摘要 + 问法 + 空路由(当前) | 75 | 11/11 | **0.7523** | 0.1844 | 14/14 | 0.5183 | question 8, summary 3 | 问法 0 / 全部 2 |
| 摘要 + 问法(无空路由) | 63 | 11/11 | **0.7523** | 0.1844 | 13/14 | 0.5183 | question 8, summary 3 | 问法 0 / 全部 2 |
| 摘要 + 简述 + 问法 + 空路由 | 82 | 11/11 | **0.7523** | 0.1838 | 14/14 | 0.5183 | question 8, summary 3 | 问法 0 / 全部 3 |
| 摘要 + 简述(无问法) | 14 | 11/11 | **0.6906** | 0.153 | 14/14 | 0.3092 | summary 10, brief 1 | 问法 0 / 全部 5 |
| 只有摘要 | 7 | 11/11 | **0.689** | 0.1601 | 14/14 | 0.3092 | summary 11 | —(每意图仅 1 面,留一法不适用) |

三条结论(都据此改了代码):

1. **相似问法确实在干活**:真人题的命中面里绝大多数是问法面,均分从 0.689 抬到 0.752、均边距 0.160 → 0.184。代价诚实写出来:负例最高分也从 0.309 抬到 0.407,安全带变窄(仍可分)—— 索引面越丰富,越容易被沾边的非问数问题蹭到分。
2. **空路由是必需项,不是优化**:「负例判对」列显示去掉空路由是 13/14 —— 漏的那一条正是 B8 逼出来的 warranty 题(§2.2)。注意均分/均边距/命中面几列完全不变:空路由**只影响该被拒的问题,不影响该被命中的问题**,这正是想要的性质。
3. **简述(brief)不入索引**:加不加它,真人题的命中/均分/均边距/负例最高分完全一样,它一次都没当过命中面,却贡献了 3 条自洽性冲突。说明书体的长段落对"问句 vs 问句"没有增益,只在相近意图之间制造噪声,所以 `build_faces()` 默认不放它。

## §3 阈值标定(实测分数分布)

| 类别 | n | min | median | mean | max |
| --- | --- | --- | --- | --- | --- |
| 正例(应命中) | 32 | 0.4981 | 0.7346 | 0.7201 | 0.9166 |
| 边界例(模板外问数,也应命中) | 5 | 0.4998 | 0.6429 | 0.6451 | 0.7557 |
| 非问数负例(取其**最高真实意图分**,应低于阈值) | 14 | 0.2106 | 0.3228 | 0.3241 | 0.5183 |

- 负例最高(真实意图)分 **0.5183** ↔ 应命中类最低分 **0.4981** → **重叠,阈值单独已不可分**
- 代码冻结阈值 **0.45**
- 正确命中的最小边距 **0.0134**;代码冻结边距 **0.03**

> ⚠ **这里现在是重叠的,而且这不是缺陷、是被 §2.2 那道加固换来的**:重叠完全由`What's the warranty period on the HC-300 battery cabinet?` 一题造成 —— 它对 i15 的相似度 0.5183,高于应命中类的最低分 0.4981。任何能拦住它的阈值都会先误杀真正例,所以这一类只能靠空路由拦(实测:去掉空路由 13/14,带上 14/14,见 §2.1 消融的「负例判对」列)。**结论:阈值不再是唯一防线,空路由是必需项而不是可选优化。**

> 负例这一行取的是"最高真实意图分"而不是 top1:空路由入索引后,负例的 top1 通常是负例面自己(分数很高,那正是它该有的样子),拿它算分离带会把带算歪。两道关是串联的 —— 空路由先拦一层,阈值仍要能独立站住。

> 两道门槛缺一不可:只有阈值 → 两个意图咬得很近时选错纯看运气;只有边距 → 跟谁都不像的问题可能"矮子里拔将军"被当成问数。

## §4 评测明细

### §4.1 正例 A:B6 的真人已审问题(11/11)

跨 stage 复用 B6 已人审的问题,顺带证明 B7 检回的意图与 B6 当时用的模板一致(端到端能接上)。

| 判 | 问题 | 期望 | top1 | 分数 | 边距 | 判定 | 命中的面 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✅ | List recent orders for Summit Logistics — only the order numbers and order dates, no other columns | i01 | i01 | 0.743 | 0.217 | confident_hit | `Summit Logistics Pty Ltd orders year to date, include order …` |
| ✅ | Movement history for SKU INV-50K at Melbourne — show only movement date, movement type and quantity, nothing else | i15 | i15 | 0.554 | 0.013 | ambiguous_margin | `Show all movements and balances for HC-50 in Sydney for 2026…` |
| ✅ | Top 10 customers by revenue over the last 12 months; drop the most recent order date column | i09 | i09 | 0.799 | 0.190 | confident_hit | `Top 10 customers by revenue last 12 months` |
| ✅ | Total outbound units per warehouse over the last 12 months, no monthly breakdown | i16 | i16 | 0.817 | 0.182 | confident_hit | `Can you show monthly outbound units by warehouse for the las…` |
| ✅ | One overall total of outbound units across all warehouses for the last 12 months | i16 | i16 | 0.802 | 0.170 | confident_hit | `Can you show monthly outbound units by warehouse for the las…` |
| ✅ | Total revenue across all customers for the last 12 months — just one number | i09 | i09 | 0.650 | 0.039 | confident_hit | `Top 10 customers by revenue last 12 months` |
| ✅ | Show me recent orders for Summit Logistics | i01 | i01 | 0.729 | 0.238 | confident_hit | `Show me the most recent orders for Summit Manufacturing Pty …` |
| ✅ | Monthly revenue trend since March 2026 | i07 | i07 | 0.788 | 0.257 | confident_hit | `Monthly revenue trend (excluding cancelled)` |
| ✅ | Monthly outbound units by warehouse for Q1 2026 | i16 | i16 | 0.855 | 0.242 | confident_hit | `Monthly outbound units trend by warehouse` |
| ✅ | Monthly outbound trend for the Sydney warehouse only, over the last 12 months | i16 | i16 | 0.797 | 0.154 | confident_hit | `Monthly outbound units trend by warehouse` |
| ✅ | What items are on order SO-2026-01281? | i02 | i02 | 0.740 | 0.325 | confident_hit | `What products are on SO-2026-01255 and how many units of eac…` |

### §4.2 正例 B:另一套 prompt 生成的改述(21/21)

生成评测题时**看不到索引里的相似问法**,只看意图摘要与简述(防自己考自己)。

⚠ 如实交代一处非预期属性:生成评测题时也没给真实取值表,所以模型编了库里没有的实体(Beta Logistics / WID-004 / WH-02 / Dallas depot / Warehouse A)。**保留不改**,因为它反而把题出难了 —— 索引里全是真实值(Summit Logistics / HC-300 / Sydney),题面用的是陌生值,能命中就说明路由靠的是**问句的形状**而不是背下来的实体名;21 题全中。若倾向用贴近真实的题面,删掉 `out/eval_questions.json` 重跑 `--all` 即可重出一套。

| 判 | 问题 | 期望 | top1 | 分数 | 边距 | 判定 | 命中的面 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✅ | acme corp recent orders last 90 days exclude cancelled sort by most recent | i01 | i01 | 0.632 | 0.088 | confident_hit | `Summit Manufacturing Pty Ltd recent orders last 90 days excl…` |
| ✅ | Please show me all orders for customer CUST-1042 from March 1–31, 2026, excluding canceled ones, with order number, date, status, and total, sorted by highest value. | i01 | i01 | 0.644 | 0.057 | confident_hit | `Recent orders for a specific customer` |
| ✅ | Can I see the latest purchase records for client “Beta Logistics” in Q2 2026, leave out voided, and list the biggest amounts first with the ref ID, placed-on date, stage, and amount? | i01 | i01 | 0.530 | 0.021 | ambiguous_margin | `Can I get the recent order history for Coastal Aggregates Pt…` |
| ✅ | order so-778899 line items sku name qty unit sell price line amount aud (active products only) | i02 | i02 | 0.736 | 0.255 | confident_hit | `Can you list all the line items on order SO-2026-01281, show…` |
| ✅ | Could you please list all line items for order SO-10234, including the product SKU and name, quantity, unit sell price, and the line amount in AUD? | i02 | i02 | 0.917 | 0.408 | confident_hit | `Can you list all the line items on order SO-2026-01281, show…` |
| ✅ | For sales order 45002117, show the products on that ticket with their code, description, units, price each, and extended amount in AUD; limit it to currently active SKUs. | i02 | i02 | 0.698 | 0.167 | confident_hit | `Can you list all the line items on order SO-2026-01281, show…` |
| ✅ | mo rev trend aud last 12 months by order date exclude cancelled | i07 | i07 | 0.583 | 0.036 | confident_hit | `Monthly revenue trend (excluding cancelled)` |
| ✅ | Please provide the monthly total booked revenue in AUD for January through June 2024 based on the order date, excluding cancelled orders. | i07 | i07 | 0.751 | 0.115 | confident_hit | `Monthly sales totals in AUD year to date, exclude cancelled …` |
| ✅ | Show month-by-month booked sales in AUD for Q1 2024 using the date ordered, skipping voided orders and focusing on settled/paid ones. | i07 | i07 | 0.733 | 0.169 | confident_hit | `Show monthly sales revenue in AUD for the last 12 months, ex…` |
| ✅ | top 10 customers by revenue last 12 months aud, exclude cancelled | i09 | i09 | 0.792 | 0.109 | confident_hit | `Top 10 customers by AUD revenue in the past year` |
| ✅ | Could you list the top 10 customers by total booked revenue in AUD from 2025-08-01 to 2026-07-31, excluding cancelled orders? | i09 | i09 | 0.832 | 0.141 | confident_hit | `Can you list our top 10 customers by booked revenue for the …` |
| ✅ | Which 10 client accounts brought in the most sales over the past year in AUD, not counting canceled orders? | i09 | i09 | 0.780 | 0.116 | confident_hit | `Top 10 customers by AUD revenue in the past year` |
| ✅ | sku wid-004 movement log warehouse wh-02 2026-05-01 to 2026-05-15 | i15 | i15 | 0.498 | 0.018 | ambiguous_margin | `I want the detailed movement log (receipts, dispatches, adju…` |
| ✅ | Please provide the stock movement ledger for SKU WID-004 at Warehouse WH-02 from May 1 to May 15, 2026. | i15 | i15 | 0.670 | 0.113 | confident_hit | `Stock movement history for a product at a warehouse` |
| ✅ | Show the item ins-and-outs at the Dallas depot for SKU WID-004 for 01–15 May 2026, including quantities, move type, dates, running on-hand, and reference. | i15 | i15 | 0.536 | 0.042 | confident_hit | `Stock movement history for a product at a warehouse` |
| ✅ | monthly outbound units by warehouse last 12 months | i16 | i16 | 0.865 | 0.203 | confident_hit | `Can you show monthly outbound units by warehouse for the las…` |
| ✅ | Please show the monthly outbound units trend for Warehouse A from 2025-01 through 2025-06. | i16 | i16 | 0.803 | 0.206 | confident_hit | `Monthly outbound units trend by warehouse` |
| ✅ | Show units shipped out each month by depot for this year, excluding the Dallas DC. | i16 | i16 | 0.646 | 0.092 | confident_hit | `Month-by-month units shipped out per warehouse, covering Bri…` |
| ✅ | top skus by shipped units last 90d | i18 | i18 | 0.719 | 0.223 | confident_hit | `Can you show top products by units shipped in the last 90 da…` |
| ✅ | Please list the top 10 products by units shipped from the Dallas DC over the last 90 days. | i18 | i18 | 0.715 | 0.137 | confident_hit | `Can you show top products by units shipped in the last 90 da…` |
| ✅ | Which items had the highest units sent out in the past three months? | i18 | i18 | 0.686 | 0.129 | confident_hit | `Give me the products with the highest outbound units in the …` |

### §4.3 非问数负例(14/14)

手写。刻意混入沾业务词的困难负例(50kW inverter / Brisbane / shipment)——只看"有没有业务名词"是分不开的。

⚠ 末尾两条是 **B8 之后补进来的**,来历不同,分开交代:
- `regression-B8-E18`(warranty period on the HC-300):就是把 §2.2 那个真实故障钉成回归守卫。它**不是独立测量** —— 空路由负例面正是知道它之后写的;它的作用是防这个坑再被踩回去。
- `hard-neg-untuned`(lead time on the ACC-METER):同一类困难负例,但**写空路由面时并没有针对它**(那批面里没有任何一条提 lead time)。它通过,才说明空路由学到的是"问产品属性 ≠ 查产品数据"这个类别,而不是背下了那一道题。

| 判 | 问题 | top1 | 分数 | 边距 | 判定 | 命中的面 |
| --- | --- | --- | --- | --- | --- | --- |
| ✅ | What is Clenergy's warranty policy for residential inverters? | __non_data__ | 0.416 | 0.088 | null_route | `Does the HC series come with an extended warranty option?` |
| ✅ | Where can I find the installation manual for the 50kW inverter? | __non_data__ | 0.537 | 0.130 | null_route | `What is the operating temperature range of the INV-250K inve…` |
| ✅ | Summarise the AS/NZS 5033 compliance requirements for rooftop arrays. | __non_data__ | 0.340 | 0.023 | null_route | `Which certifications does the PowerCab cabinet hold for the …` |
| ✅ | What does error code E014 mean on the inverter display? | __non_data__ | 0.690 | 0.351 | null_route | `What does a flashing red LED on the inverter mean?` |
| ✅ | Explain how MPPT works in a solar inverter. | __non_data__ | 0.426 | 0.178 | null_route | `What does a flashing red LED on the inverter mean?` |
| ✅ | Who should I contact about a damaged shipment? | __non_data__ | 0.575 | 0.296 | null_route | `Who do I escalate a customer complaint to?` |
| ✅ | How do I reset my password? | __non_data__ | 0.265 | 0.046 | null_route | `Who do I escalate a customer complaint to?` |
| ✅ | How many days of annual leave do I get? | __non_data__ | 0.326 | 0.115 | null_route | `What are the public holidays in Queensland this year?` |
| ✅ | What are the office hours over the Christmas shutdown? | __non_data__ | 0.396 | 0.125 | null_route | `What are the public holidays in Queensland this year?` |
| ✅ | Can you help me draft an email to a supplier? | __non_data__ | 0.626 | 0.220 | null_route | `Can you write a follow-up email to a distributor?` |
| ✅ | What's the weather in Brisbane today? | __non_data__ | 0.453 | 0.086 | null_route | `What are the public holidays in Queensland this year?` |
| ✅ | Book a meeting room for tomorrow afternoon. | i07 | 0.281 | 0.084 | below_hit_threshold | `Trend of booked revenue per calendar month for 2025.` |
| ✅ | What's the warranty period on the HC-300 battery cabinet? | __non_data__ | 0.579 | 0.060 | null_route | `Does the HC series come with an extended warranty option?` |
| ✅ | What's the typical lead time on the ACC-METER smart meter? | __non_data__ | 0.467 | 0.122 | null_route | `How do I wire the Monitoring Gateway G2 to a third-party met…` |

### §4.4 边界例:模板外问数(5/5)

这 5 题来自 B6 的越界攻击集。**它们应该在这里命中最近的意图**(它们语义上确实是问数),然后由 B6 planner 判 feasible=false 干净拒答 —— 检索层不替 B6 判"能不能答"。

| 判 | 问题 | 期望 | top1 | 分数 | 边距 | 判定 | 命中的面 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✅ | Show recent orders for Summit Logistics including the sales rep name | i01 | i01 | 0.643 | 0.161 | confident_hit | `Show me the most recent orders for Summit Manufacturing Pty …` |
| ✅ | Monthly revenue for NSW customers only | i07 | i07 | 0.584 | 0.030 | confident_hit | `Monthly revenue trend AUD, 2025-01 to 2025-12, exclude cance…` |
| ✅ | Monthly revenue split by sales rep | i07 | i07 | 0.500 | 0.018 | ambiguous_margin | `Monthly revenue trend (excluding cancelled)` |
| ✅ | Monthly outbound units for the Perth warehouse | i16 | i16 | 0.756 | 0.162 | confident_hit | `Compare outbound units per month by warehouse, Melbourne onl…` |
| ✅ | Line items for order SO-2026-01281, and include each product's unit cost and profit margin | i02 | i02 | 0.743 | 0.337 | confident_hit | `Give me all products on order SO-2026-01281 with their quant…` |

## §5 机制披露(以下内容由代码常量渲染,防文档漂移)

### 判定规则

```
每意图得分 = 其所有索引面的 max 余弦相似度(向量已归一化,余弦 = 点积)
top1 落在空路由面 `__non_data__` 上                 → is_data_question=False(reason=null_route,优先于阈值)
top1 < HIT_THRESHOLD(0.45)                → is_data_question=False(交回 S4 路由)
top1 ≥ 阈值 且 top1-top2 < MARGIN(0.03) → is_data_question=True, confident=False(返 top-3 候选,留 LLM 复核后手)
否则                                                     → confident=True(直接走该意图的模板)
```

输出形状(对齐 S4 路由要件):

```json
{
  "question": "List recent orders for Summit Logistics — only the order numbers and order dates, no other columns",
  "is_data_question": true,
  "confident": true,
  "reason": "confident_hit",
  "top1_score": 0.7432,
  "margin": 0.2169,
  "candidates": [
    {
      "intent_id": "i01",
      "score": 0.7432,
      "matched_face": "Summit Logistics Pty Ltd orders year to date, include order number, date, status, and total, sorted by highest value.",
      "face_kind": "question"
    },
    {
      "intent_id": "i09",
      "score": 0.5263,
      "matched_face": "Show the top 10 customers by total order value year to date.",
      "face_kind": "question"
    },
    {
      "intent_id": "i02",
      "score": 0.5248,
      "matched_face": "Line items for an order number",
      "face_kind": "summary"
    }
  ]
}
```

### 相似问法生成 prompt(`s3dev/questions.py: SYSTEM_PROMPT`)

```
You expand the retrieval surface of a data-question router.

A business intelligence assistant holds a fixed set of verified SQL templates. Each template
answers one INTENT. At runtime a user question is matched against indexed phrasings of every
intent, and the closest intent's template is used. Your job: write 8 alternative ways a real
employee at an Australian solar-equipment company would ask for exactly what THIS intent answers.

Rules:
1. Same information need, different wording. Every phrasing must be fully answered by this
   intent's template — no broader, no narrower, no extra dimension the template does not have.
2. Never widen a question by dropping what it is about. If the intent is "monthly outbound units
   by warehouse", then "How is our inventory doing?" is WRONG: it invites answers this template
   cannot give and will hijack unrelated questions. Keep every qualifier that makes the intent
   what it is (the entity, the measure, the grouping).
3. Must NOT fit any sibling intent listed below. A phrasing that could equally well be answered
   by a sibling is poison for the router — it makes the two intents indistinguishable. When two
   intents are close, keep the word that separates them (e.g. "by warehouse" vs "by product").
4. Vary the surface form, not the meaning: synonyms, word order, question vs. imperative.
   Include at least one short keyword-style phrasing ("Sydney outbound volume by month") and at
   least one full natural sentence ("Can you show me how many units we shipped out of each
   warehouse each month?"). Use everyday business words (shipped out, sales, best customers),
   not the database's column names.
5. Runtime parameters are free to vary — the rewriter fills them in. So DO include phrasings
   that name a concrete customer, warehouse, product, order or period (e.g. "last quarter",
   "for Sydney", "since March"). Two hard limits:
   a. Use ONLY the real values listed under real_values below. Never invent a customer name,
      product, SKU, warehouse city or order number — this company has exactly the customers,
      products and warehouses listed, and a made-up one makes the phrasing nonsense. Refer to a
      product the way a person would — by its SKU *or* by its name, never both glued together.
   b. Do NOT invent a filter the template does not have (e.g. a state, a sales rep, a cost or
      margin) — that would teach the router a question it cannot answer.
6. English only. One question per item, no numbering, no surrounding quotes.
```

### 生成时喂给模型的真实取值表(`s3dev/questions.py: value_book()`,现查演示库)

第一轮生成没有这张表,模型编出了 Perth / Adelaide / Hobart 仓库和不存在的客户与产品;相似问法是会被人审、会进演示的资产,编造值既误导审阅者,也教会路由器一堆库里没有的说法。

```json
{
  "customers": [
    "Summit Manufacturing Pty Ltd",
    "Summit Logistics Pty Ltd",
    "Boomerang Manufacturing Pty Ltd",
    "Boomerang Textiles Pty Ltd",
    "Coastal Aggregates Pty Ltd",
    "Pacific Dairy Co-op Pty Ltd"
  ],
  "order_numbers": [
    "SO-2026-01281",
    "SO-2026-01270",
    "SO-2026-01255"
  ],
  "product_skus": [
    "HC-50",
    "HC-100",
    "HC-215",
    "HC-300",
    "HC-500",
    "HC-1000"
  ],
  "product_names": [
    "PowerCab HC-50 Battery Cabinet 50kWh",
    "PowerCab HC-100 Battery Cabinet 100kWh",
    "PowerCab HC-215 Battery Cabinet 215kWh",
    "PowerCab HC-300 Battery Cabinet 300kWh",
    "PowerCab HC-500 Battery Cabinet 500kWh",
    "PowerCab HC-1000 Battery Cabinet 1MWh"
  ],
  "warehouses": [
    "Brisbane",
    "Melbourne",
    "Sydney"
  ],
  "product_categories": [
    "accessory",
    "battery_cabinet",
    "ems_software",
    "inverter"
  ],
  "order_statuses": [
    "cancelled",
    "completed",
    "paid",
    "pending",
    "shipped"
  ],
  "movement_types": [
    "adjustment",
    "inbound",
    "outbound"
  ],
  "data_window": "2024-09-01 to 2026-08-23 (today is 2026-08-23)"
}
```

### 评测题生成 prompt(`run_b7_retrieve.py: PARAPHRASE_PROMPT`,与上面刻意不同)

```
You are writing a TEST SET for a data-question router (not the router's own training data).

Given one analytics intent, write 3 questions a busy employee might actually type to get exactly
that answer. Make the three deliberately different in register:
  1. telegraphic, lower-case, keyword-ish, the way someone types in a hurry;
  2. one full polite sentence that names a concrete value (a customer, warehouse, product or period);
  3. one that uses everyday business synonyms instead of the words in the intent summary.

Every question must be fully answered by this intent — do not widen it, do not ask for a
dimension or measure the intent does not mention. English only, no numbering.
```

### 产物

| 文件 | 内容 |
| --- | --- |
| `out/intent_questions/{id}.json` | **相似问法资产**(人可直接编辑;Phase C 落库、Phase D 前端可编辑) |
| `out/non_data_faces.json` | **空路由负例面**(人可编辑;Phase C 与相似问法一起落库) |
| `out/eval_questions.json` | 固定评测集(生成一次即冻结,分数才可比) |
| `out/retrieval_eval.json` | 本轮全部评测结果与标定数据 |
| `out/embed_cache.json` | embedding 缓存(同一文本永远同一向量,`--check` 逐字可复现) |
