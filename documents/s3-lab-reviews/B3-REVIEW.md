# B3 意图 candidate 评审报告

- 生成于 2026-08-23T16:36:40;共 20 条(9 查询 query / 11 统计 stats)
- 生成批次:run1: orders,order_items,products,customers,sales_reps(12 条);run2: inventory,stock_movements,products(8 条)
- **审核要点**:分型是否正确(查询=无分组明细,统计=有分组聚合);是否像平时真会问的问题;
  覆盖是否全面。**勾选 6–8 条采纳**(查询/统计大致各半),告诉我 id 即可定稿。
- 盲判说明:`盲判` 列是 gpt-5-mini 只看 brief(不见 type/前缀)判『是否需要 GROUP BY』,
  与声明 type 不一致的会标 ⚠️,供人工重点复核。

## Run 1:选表 `orders, order_items, products, customers, sales_reps`

| id | 查询/统计 | 覆盖桶 | one-liner | 涉及表 | 盲判 |
|---|---|---|---|---|---|
| i01 | **查询** Query | multi_table_query | Query: Recent orders for a specific customer | orders, customers | 无GB ✓ |
| i02 | **查询** Query | multi_table_query | Query: Line items for an order number | orders, order_items, products | 无GB ✓ |
| i03 | **查询** Query | single_table_query | Query: Active products by category or series with price filter | products | 无GB ✓ |
| i04 | **查询** Query | single_table_query | Query: New customer accounts created in a period | customers | 无GB ✓ |
| i05 | **查询** Query | multi_table_query | Query: Orders handled by a specific sales rep | orders, sales_reps | 无GB ✓ |
| i06 | **查询** Query | multi_table_query | Query: Price realisation: items sold below/above list by threshold | order_items, products, orders | 无GB ✓ |
| i07 | **统计** Stats | time_stats | Stats: Monthly revenue trend (excluding cancelled) | orders | GROUP BY ✓ |
| i08 | **统计** Stats | category_stats | Stats: Revenue by product category | order_items, products, orders | GROUP BY ✓ |
| i09 | **统计** Stats | ranking_stats | Stats: Top 10 customers by revenue (last 12 months) | orders, customers | GROUP BY ✓ |
| i10 | **统计** Stats | category_stats | Stats: Average selling price by product (ASP) | order_items, products, orders | GROUP BY ✓ |
| i11 | **统计** Stats | category_stats | Stats: Revenue and order count by customer state | orders, customers | GROUP BY ✓ |
| i12 | **统计** Stats | ranking_stats | Stats: Top sales reps by revenue and orders | orders, sales_reps | GROUP BY ✓ |

**i01**(**查询** Query)Query: Recent orders for a specific customer

> Returns detailed orders for a chosen customer, including order number, date, status, and order total. Users typically vary the customer (by name or ID), a date range, and statuses to include or exclude (e.g., exclude cancelled). Results can be sorted by most recent or highest value.

**i02**(**查询** Query)Query: Line items for an order number

> Lists all product lines on a given order: product SKU/name, quantity, unit sell price, and line amount in AUD. Users provide an order number and may also filter to active products only for validation.

**i03**(**查询** Query)Query: Active products by category or series with price filter

> Shows active products that match a selected category or series, with optional minimum/maximum list price in AUD. Useful for quickly viewing the current sellable range in a pricing band.

**i04**(**查询** Query)Query: New customer accounts created in a period

> Lists customer accounts onboarded within a chosen date range, with their name, state, channel type, and industry. Users typically filter by state or channel to see recent additions in their territory.

**i05**(**查询** Query)Query: Orders handled by a specific sales rep

> Returns orders attributed to a selected sales rep with order number, date, status, and total amount in AUD. Users vary the rep, date range, and status filters to review that rep’s pipeline or completed sales.

**i06**(**查询** Query)Query: Price realisation: items sold below/above list by threshold

> Lists order items where the actual unit sell price deviates from the product list price by more than a chosen percentage (e.g., >10% discount or premium). Users vary the date range and may restrict to active products or a product series.

**i07**(**统计** Stats)Stats: Monthly revenue trend (excluding cancelled)

> Aggregates total booked revenue per calendar month based on order date, summing order totals in AUD and excluding orders with status cancelled. Users vary the date range and may filter by status to focus on completed/paid bookings.

**i08**(**统计** Stats)Stats: Revenue by product category

> Summarises sales by product category, summing line amounts in AUD for items on orders that are not cancelled. Users vary the date range and may include filters for product series or active products.

**i09**(**统计** Stats)Stats: Top 10 customers by revenue (last 12 months)

> Ranks customers by total booked revenue in AUD over a chosen period (commonly the last 12 months), excluding cancelled orders. Aggregation is the sum of order totals per customer; ties can be broken by most recent order date.

**i10**(**统计** Stats)Stats: Average selling price by product (ASP)

> Calculates the average realised unit sell price per product (SKU) over a selected date range, using order item unit prices from orders that are not cancelled. Useful for tracking discounting and price positioning versus list.

**i11**(**统计** Stats)Stats: Revenue and order count by customer state

> Groups sales by the customer’s Australian state, returning total revenue in AUD and number of orders for a selected period, excluding cancelled. Helps compare performance across NSW, VIC, QLD, SA, and WA.

**i12**(**统计** Stats)Stats: Top sales reps by revenue and orders

> Ranks sales reps over a chosen date range by total booked revenue in AUD and number of orders, excluding cancelled. Aggregations are sum of order totals and count of orders per rep to compare performance across the team.

## Run 2:选表 `inventory, stock_movements, products`

| id | 查询/统计 | 覆盖桶 | one-liner | 涉及表 | 盲判 |
|---|---|---|---|---|---|
| i13 | **查询** Query | multi_table_query | Query: Current stock by warehouse for a specific product | inventory, products | 无GB ✓ |
| i14 | **查询** Query | single_table_query | Query: Low available stock items by warehouse | inventory | 无GB ✓ |
| i15 | **查询** Query | single_table_query | Query: Stock movement history for a product at a warehouse | stock_movements | 无GB ✓ |
| i16 | **统计** Stats | time_stats | Stats: Monthly outbound units trend by warehouse | stock_movements | GROUP BY ✓ |
| i17 | **统计** Stats | category_stats | Stats: Inventory value by product category | inventory, products | GROUP BY ✓ |
| i18 | **统计** Stats | ranking_stats | Stats: Top products by outbound units (last 90 days) | stock_movements, products | GROUP BY ✓ |
| i19 | **统计** Stats | ranking_stats | Stats: Products with the highest available stock across warehouses | inventory, products | GROUP BY ✓ |
| i20 | **统计** Stats | time_stats | Stats: Monthly net adjustment impact by warehouse | stock_movements | GROUP BY ✓ |

**i13**(**查询** Query)Query: Current stock by warehouse for a specific product

> Returns the latest on-hand and reserved quantities for the selected product across Sydney, Melbourne, and Brisbane warehouses. Users typically filter by a specific product (by SKU or name) and may narrow to one warehouse. It shows current availability where available = on_hand_qty minus reserved_qty to indicate what can be allocated now.

**i14**(**查询** Query)Query: Low available stock items by warehouse

> Lists inventory rows where available stock is at or below a chosen threshold for each warehouse location. Users vary the warehouse (or all), the availability threshold (e.g., <= 5 units), and can filter to active products only if needed via a separate view. Availability is calculated as on_hand_qty minus reserved_qty.

**i15**(**查询** Query)Query: Stock movement history for a product at a warehouse

> Shows the chronological ledger of movements for a chosen product at one warehouse over a date range, including movement date, type (inbound/outbound/adjustment), quantity, running balance after, and source reference. Users typically set the product, warehouse, and time window to investigate receipts, deliveries, or stocktakes. Useful for tracing discrepancies or confirming dispatches.

**i16**(**统计** Stats)Stats: Monthly outbound units trend by warehouse

> Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses.

**i17**(**统计** Stats)Stats: Inventory value by product category

> Summarises current inventory investment by business category. Groups by product category and sums available units (on_hand_qty minus reserved_qty) multiplied by list price (AUD, ex GST) to approximate recoverable stock value. Users can filter by warehouse or focus on active products only.

**i18**(**统计** Stats)Stats: Top products by outbound units (last 90 days)

> Ranks products by shipment volume over a recent period. Groups by product and sums quantity where movement_type is outbound within the chosen window (e.g., last 90 days), then orders descending to return the top N products; this reflects units shipped to customers. Users vary the lookback window and optionally limit to certain warehouses.

**i19**(**统计** Stats)Stats: Products with the highest available stock across warehouses

> Ranks products by total available units on hand across all warehouses. Groups by product and sums availability defined as on_hand_qty minus reserved_qty; this highlights items tying up the most stock or ready for large orders. Users can limit to active products or a specific category/series.

**i20**(**统计** Stats)Stats: Monthly net adjustment impact by warehouse

> Shows the effect of stocktake and correction activities over time. Groups by year–month and warehouse, summing quantity where movement_type is adjustment; positive totals indicate net increases from adjustments, negatives indicate write‑downs. Users vary the date range and may compare warehouses to detect systemic issues.

---

## 附:生成机制全披露(每一批 intents 是怎么来的)

> 本节内容全部由代码中的真实常量/函数渲染(`s3dev/intents.py`),不是手写转述。
> 每次实际调用的完整输入输出原文都落盘在 `out/llm_log/`(生成 `*-b3-gen-*.json`、盲判 `*-b3-judge-gb-*.json`、判重 `*-b3-judge-dup-*.json`)。

### 1. 每次生成的输入 = 两条消息

**system 消息(全文,固定不变——LLM 的全部决策规则都写在这里)**:

```text
You are helping a business user of a Text2SQL platform define "question intents"
over the database tables they selected. Each intent is a reusable question pattern that will
later become exactly one SQL template, so every intent must be answerable by a single SELECT.

There are exactly two types. Decide the type FIRST, then write the wording:
- "query": returns detail rows; the SQL would have NO GROUP BY. Filtering, sorting, or
  top-N by a stored column value are still query.
- "stats": aggregates rows into groups; the SQL REQUIRES GROUP BY (counts / sums / averages
  per month, per category, per rep..., or rankings by an aggregated measure).

Typing examples:
- "Look up recent orders of a customer" -> query
- "Top 10 products by total sales amount" -> stats (SUM aggregated per product)
- "Show the stock movement history of a product" -> query
- "Monthly order count trend" -> stats
- "List products priced above 1000 AUD" -> query (sorting/filtering only)

Each intent must have:
- type: "query" | "stats"
- bucket: coverage bucket, one of single_table_query / multi_table_query (type must be query)
  and time_stats / category_stats / ranking_stats (type must be stats). Spread intents across
  buckets; never leave a bucket empty when the requested count allows covering all.
- one_liner: MUST start with the keyword "Query: " or "Stats: " matching the type, followed
  by one short sentence a user would instantly recognize in a picker list.
- brief: 2-3 sentences stating exactly what the question returns, which conditions a user would
  typically vary when asking it (time range, status, a specific product/customer/rep, ...), and
  for stats the grouping dimension(s) and the aggregation measure with its business meaning
  (e.g. revenue = sum of order line amounts excluding cancelled orders). The brief later drives
  SQL generation, so be precise; never mention SQL keywords, describe the business meaning.
- tables: the minimal subset of the SELECTED tables the question needs (join tables included).

Rules:
- Use ONLY the selected tables and their listed columns; if a natural question would need an
  unselected table, do not propose it.
- Questions must be ones an Australian sales/operations manager would genuinely ask.
- No two intents may be near-duplicates of each other or of the AVOID list (if given).
- English only.
```

**user 消息(每次变化的数据载荷)**,四个字段:

| 字段 | 内容 | 来源 |
|---|---|---|
| `business_context` | 一句话业务背景(Clenergy 光伏支架、澳洲、AUD) | 代码常量,对应产品里数据源配置的背景说明 |
| `selected_tables` | **所选表的语义层子集**:每表 description + 每列 name/display_name/description/type/枚举逐值含义,外加仅涉所选表的表间关系 | B2 定稿 `semantic_layer.json` |
| `how_many_intents` | 要生成几条 | CLI `--n` |
| `avoid_duplicating_these_existing_intents` | 已有候选的 one-liner 清单(首批为 null) | 追加批去重用 |

**Run 1 实际 user 载荷**(选表 orders, order_items, products, customers, sales_reps;篇幅所限第 1 张表全文展开、其余同构省略——完整原文见 llm_log):

```json
{
 "business_context": "Clenergy is an Australian manufacturer of solar PV mounting systems. This database covers its sales side: products (mounting kits, inverters, energy-management gear, accessories), customers, sales reps, orders with line items, and warehouse inventory with a stock-movement ledger. Amounts are in AUD.",
 "selected_tables": {
  "tables": [
   {
    "name": "customers",
    "description": "Each row represents a customer account in Australia that Clenergy sells to or through. The table stores customer identity, location (state), sales channel, industry segment, and the date the account was created. It links to orders so sales can be attributed to the correct customer.",
    "columns": [
     {
      "name": "id",
      "display_name": "Customer ID",
      "description": "System-generated unique identifier for the customer account. Referenced by orders.customer_id to link each order to this customer.",
      "type": "int unsigned",
      "enum_values": null
     },
     {
      "name": "name",
      "display_name": "Customer Name",
      "description": "Legal or trading name of the customer, as stored in the CRM/ERP. Text up to 128 characters.",
      "type": "varchar(128)",
      "enum_values": null
     },
     {
      "name": "state",
      "display_name": "State",
      "description": "Australian state: NSW / VIC / QLD / SA / WA",
      "type": "varchar(3)",
      "enum_values": [
       {
        "value": "NSW",
        "meaning": "New South Wales."
       },
       {
        "value": "QLD",
        "meaning": "Queensland."
       },
       {
        "value": "SA",
        "meaning": "South Australia."
       },
       {
        "value": "VIC",
        "meaning": "Victoria."
       },
       {
        "value": "WA",
        "meaning": "Western Australia."
       }
      ]
     },
     {
      "name": "channel_type",
      "display_name": "Channel Type",
      "description": "Sales channel relationship for this customer account. Indicates whether Clenergy sells to this account directly or via distribution.",
      "type": "varchar(16)",
      "enum_values": [
       {
        "value": "direct",
        "meaning": "Clenergy sells directly to this customer (end account)."
       },
       {
        "value": "distributor",
        "meaning": "The customer is a distributor/reseller purchasing for onward sale."
       }
      ]
     },
     {
      "name": "industry",
      "display_name": "Industry",
      "description": "Primary industry segment for the customer account. Used for segmentation and reporting.",
      "type": "varchar(32)",
      "enum_values": [
       {
        "value": "agriculture",
        "meaning": "Farms and agricultural producers or agribusiness operations."
       },
       {
        "value": "commercial_complex",
        "meaning": "Shopping centres, office parks, or mixed-use commercial complexes."
       },
       {
        "value": "factory",
        "meaning": "Manufacturing plants and production facilities."
       },
       {
        "value": "industrial_park",
        "meaning": "Multi-tenant industrial estates or business parks."
       },
       {
        "value": "logistics",
        "meaning": "Warehousing, distribution, and freight/logistics operators."
       }
      ]
     },
     {
      "name": "created_at",
      "display_name": "Created Date",
      "description": "Date the customer record was created/onboarded (YYYY‑MM‑DD, day-level). Useful for cohorting and account age analysis.",
      "type": "date",
      "enum_values": null
     }
    ]
   },
   "…(其余 4 张表同构:order_items, orders, products, sales_reps)"
  ],
  "relations": [
   {
    "from": "order_items.order_id",
    "to": "orders.id"
   },
   {
    "from": "order_items.product_id",
    "to": "products.id"
   },
   {
    "from": "orders.customer_id",
    "to": "customers.id"
   },
   {
    "from": "orders.sales_rep_id",
    "to": "sales_reps.id"
   }
  ]
 },
 "how_many_intents": 12,
 "avoid_duplicating_these_existing_intents": null
}
```

**Run 2(追加批)与 Run 1 的仅有差异**:`selected_tables` 换成 inventory, stock_movements, products 的语义层子集;`avoid_duplicating_these_existing_intents` = Run 1 全部 12 条 one-liner (system 规则要求不得与其近似重复)。

### 2. LLM 被要求的决策顺序(system 消息强制)

1. **先定 type,再写文案**:该问题的 SQL 需要 GROUP BY(按月/按类/按人聚合或按聚合值排名)→ `stats`;只是过滤/排序/取明细(含按已存列取 top-N)→ `query`。system 里给了 5 个判例锚定边界(如"按总销售额取 Top 10 产品"是 stats,"列出价格高于 1000 的产品"是 query);
2. **选覆盖桶**:五个桶(单表查询/多表查询/时间统计/分类统计/排名统计)要求铺开,不许挤在一两类;桶名自带类型(`*_query`/`*_stats`),桶选错会被机器校验当场打回;
3. **圈最小表集**:只能用所选表;问题若天然需要未选的表,就不许提这个问题;
4. **写 one-liner**:必须以关键字 `Query: ` / `Stats: ` 领跑(与 type 一致),后接一句用户在列表里一眼能认出的话;
5. **写 brief(2–3 句,后续直接驱动 B4 生成 SQL)**:必须写清返回什么、用户通常会变哪些条件(时间段/状态/某个产品或客户),stats 型必须写清分组维度 + 聚合口径的业务含义(如 revenue = 排除 cancelled 的订单金额合计);不许出现 SQL 关键词;
6. **避重**:不得与本批其他条目或 avoid 清单近似重复;全英文。

### 3. 输出 = json_schema 强制的结构化 JSON

响应格式用 OpenAI structured output 锁死(`INTENT_SCHEMA`),每条必含 5 个字段:

```json
{
 "type": "object",
 "required": [
  "type",
  "bucket",
  "one_liner",
  "brief",
  "tables"
 ],
 "properties": {
  "type": {
   "type": "string",
   "enum": [
    "query",
    "stats"
   ]
  },
  "bucket": {
   "type": "string",
   "enum": [
    "single_table_query",
    "multi_table_query",
    "time_stats",
    "category_stats",
    "ranking_stats"
   ]
  },
  "one_liner": {
   "type": "string"
  },
  "brief": {
   "type": "string"
  },
  "tables": {
   "type": "array",
   "items": {
    "type": "string"
   }
  }
 }
}
```

实际输出示例(i01,LLM 原样返回,`id/run` 为落盘时程序追加):

```json
{
 "type": "query",
 "bucket": "multi_table_query",
 "one_liner": "Query: Recent orders for a specific customer",
 "brief": "Returns detailed orders for a chosen customer, including order number, date, status, and order total. Users typically vary the customer (by name or ID), a date range, and statuses to include or exclude (e.g., exclude cancelled). Results can be sorted by most recent or highest value.",
 "tables": [
  "orders",
  "customers"
 ]
}
```

### 4. 生成后的机器校验(不过 → 问题清单回灌重试,最多共 3 次调用)

- 条数 = 要求条数;
- one-liner 前缀与 type 一致(`Query: `/`Stats: `);
- 桶与 type 映射一致(`single_table_query`/`multi_table_query` 必须 query,`time_stats`/`category_stats`/`ranking_stats` 必须 stats);
- tables 非空且 ⊆ 本批所选表;
- brief ≥ 40 字符(两三句的下限);
- 全英文(扫 CJK 字符);不得逐字重复 avoid 清单。

### 5. 独立判卷(自测,gpt-5-mini,与生成模型互相独立)

**盲判 GROUP BY**:只给每条的 brief(**剥掉前缀、不给 type/桶**),独立判"SQL 是否需要 GROUP BY",再与声明 type 比对——文案与分型不符会被抓出来,不靠生成模型自己说了算。判卷 system 全文:

```text
For each item, decide from the question brief alone whether answering it in SQL requires GROUP BY (aggregating rows per group: per month / per category / per entity, or ranking by an aggregated measure). Detail listings, filters, sorting and top-N by a stored column do NOT need GROUP BY. Return a verdict per id.
```

**追加批判重**:给已有候选与新候选的 one-liner+brief,判"是否同一问题模式问同一份数据(一个 SQL 模板能同时服务)"。判卷 system 全文:

```text
For each NEW intent, decide whether it substantially duplicates one of the EXISTING intents — i.e. the same question pattern over the same data, so one SQL template would serve both. Different grouping dimension, different measure, or a different subject table is NOT a duplicate. Return duplicate_of = the existing id, else null.
```
