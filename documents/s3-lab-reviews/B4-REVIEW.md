# B4 评审:SQL 模板(已采纳意图 → 可运行模板)

> 生成锚点日期 **2026-08-23**(绝对时间默认值以此回推);演示库数据范围 2024-09-01 ~ 2026-08-23。
> 全部 LLM 原始调用在 `out/llm_log/`(tag `b4-*`)。生成机制全披露见文末附录。

**人审三问(每条模板)**:① join 路径对不对;② brief 里的每条口径都落实了吗(对照『口径落实』逐条勾);③ WHERE 默认条件与默认值合理吗。
**定稿动作**:认可后我把草稿定稿到 `out/templates/`;要手改 SQL 就直接改 `out/template_drafts/{id}.json` 的 sql 字段(改完我跑 `--check` 复验),或直接告诉我改什么。

| id | 类型 | one-liner | 表 | 静态校验 | 试执行 | 自修轮数 |
|---|---|---|---|---|---|---|
| i01 | **查询** Query | Query: Recent orders for a specific customer | orders, customers | ✅ | 4 行 | 0 |
| i02 | **查询** Query | Query: Line items for an order number | orders, order_items, products | ✅ | 1 行 | 0 |
| i07 | **统计** Stats | Stats: Monthly revenue trend (excluding cancelled) | orders | ✅ | 13 行 | 0 |
| i09 | **统计** Stats | Stats: Top 10 customers by revenue (last 12 months) | orders, customers | ✅ | 10 行 | 0 |
| i15 | **查询** Query | Query: Stock movement history for a product at a warehouse | stock_movements, products | ✅ | 26 行 | 0 |
| i16 | **统计** Stats | Stats: Monthly outbound units trend by warehouse | stock_movements | ✅ | 39 行 | 1 |
| i18 | **统计** Stats | Stats: Top products by outbound units (last 90 days) | stock_movements, products | ✅ | 10 行 | 0 |


---

## i01 — Query: Recent orders for a specific customer

> **brief(口径契约)**:Returns detailed orders for a chosen customer, including order number, date, status, and order total. Users typically vary the customer (by name or ID), a date range, and statuses to include or exclude (e.g., exclude cancelled). Results can be sorted by most recent or highest value.

### 最终 SQL

```sql
SELECT
  c.name AS customer_name,
  o.order_no AS order_number,
  o.order_date AS order_date,
  o.status AS order_status,
  o.total_amount AS order_total_aud
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.id
WHERE
  c.name LIKE '%Bluegum Beverages Pty Ltd%'
  AND o.order_date >= '2025-08-23'
  AND o.status IN ('completed', 'paid', 'pending', 'shipped')
ORDER BY
  o.order_date DESC,
  o.total_amount DESC
LIMIT 50
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:orders o JOIN customers c ON o.customer_id = c.id

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `customers.name` | `LIKE` | `%Bluegum Beverages Pty Ltd%` | Users identify the customer by name; default to a concrete example that exists. |
| `orders.order_date` | `>=` | `2025-08-23` | Show recent activity by default (last 12 months from 2026-08-23). |
| `orders.status` | `IN` | `('completed', 'paid', 'pending', 'shipped')` | Exclude cancelled orders by default while including common active/closed states. |

**口径落实**(应与 brief 一一对应):

- Includes order number, date, status, and total as required.
- Customer can be varied by human-facing name (LIKE) per guidance; users may adjust the literal to target a different customer.
- Date range is implemented via a start-date predicate to enable narrowing or broadening the window.
- Status inclusion/exclusion implemented via a single IN list; cancelled is excluded by default.
- Sorted by most recent orders (order_date DESC); this satisfies the brief’s recency sort option.
- Amounts are shown as stored in AUD; no currency conversion.

### 试执行(真库 biz_reader 只读)—— 共 **4** 行,前 4 行:

| customer_name | order_number | order_date | order_status | order_total_aud |
|---|---|---|---|---|
| Bluegum Beverages Pty Ltd | SO-2026-01138 | 2026-05-08 | completed | 58176.22 |
| Bluegum Beverages Pty Ltd | SO-2026-00890 | 2026-01-31 | completed | 368112.81 |
| Bluegum Beverages Pty Ltd | SO-2025-00709 | 2025-10-30 | completed | 1064033.62 |
| Bluegum Beverages Pty Ltd | SO-2025-00707 | 2025-10-02 | completed | 5253.80 |

### 自修轨迹

一次通过,无自修。


---

## i02 — Query: Line items for an order number

> **brief(口径契约)**:Lists all product lines on a given order: product SKU/name, quantity, unit sell price, and line amount in AUD. Users provide an order number and may also filter to active products only for validation.

> ✏️ **此条含人工手改**:Reviewer edit (2026-08-23): is_active default relaxed to IN (0, 1) so the optional active-only validation never hides order lines by default.

### 最终 SQL

```sql
SELECT
  o.order_no AS order_number,
  p.sku AS product_sku,
  p.name AS product_name,
  oi.quantity AS quantity,
  oi.unit_price AS unit_sell_price_aud,
  oi.line_amount AS line_amount_aud
FROM order_items AS oi
JOIN orders AS o
  ON oi.order_id = o.id
JOIN products AS p
  ON oi.product_id = p.id
WHERE
  o.order_no = 'SO-2024-00001' AND p.is_active IN (0, 1)
ORDER BY
  oi.id ASC
LIMIT 50
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:order_items oi JOIN orders o ON oi.order_id = o.id JOIN products p ON oi.product_id = p.id

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `orders.order_no` | `=` | `SO-2024-00001` | Users identify the order by its business order number. |
| `products.is_active` | `IN` | `(0, 1)` | Kept as a rewritable parameter but non-restrictive by default so no order lines are hidden; narrow to 1 to validate active products only. |

**口径落实**(应与 brief 一一对应):

- Lists product SKU, product name, quantity, unit sell price, and line amount for the specified order.
- Users provide an order number; filtering is on the human-facing order_no.
- Active-product validation is available via products.is_active but defaults to include both active and inactive, so every line on the order is shown.
- All amounts are shown as stored in AUD; no conversion.
- Detail query with no aggregation; ordered by line sequence (order_items.id) and limited to 50 rows.

### 试执行(真库 biz_reader 只读)—— 共 **1** 行,前 1 行:

| order_number | product_sku | product_name | quantity | unit_sell_price_aud | line_amount_aud |
|---|---|---|---|---|---|
| SO-2024-00001 | HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | 4 | 166352.19 | 665408.76 |

### 自修轨迹

一次通过,无自修。


---

## i07 — Stats: Monthly revenue trend (excluding cancelled)

> **brief(口径契约)**:Aggregates total booked revenue per calendar month based on order date, summing order totals in AUD and excluding orders with status cancelled. Users vary the date range and may filter by status to focus on completed/paid bookings.

> ✏️ **此条含人工手改**:Reviewer edit (2026-08-23): replaced status IN (4 values) with status != 'cancelled' to match the brief verbatim (equivalent on current enum).

### 最终 SQL

```sql
SELECT
  DATE_FORMAT(o.order_date, '%Y-%m') AS month,
  SUM(o.total_amount) AS total_revenue_aud
FROM orders AS o
WHERE
  o.order_date >= '2025-08-23' AND o.status <> 'cancelled'
GROUP BY
  DATE_FORMAT(o.order_date, '%Y-%m')
ORDER BY
  month ASC
LIMIT 200
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:(单表,无 join)
- **度量口径**:
  - `SUM(o.total_amount)` — Total booked revenue in AUD per calendar month, summing order totals.
- **分组维度**:`DATE_FORMAT(o.order_date, '%Y-%m')`

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `orders.order_date` | `>=` | `2025-08-23` | Default trend window: last 12 months up to 2026-08-23. |
| `orders.status` | `!=` | `cancelled` | Brief excludes cancelled orders from booked revenue; all other statuses count. |

**口径落实**(应与 brief 一一对应):

- Excludes orders with status cancelled via status != 'cancelled', matching the brief verbatim.
- Revenue is summed from orders.total_amount (AUD).
- Grain is calendar month using order_date.
- Orders with status cancelled are excluded via a positive allowlist on status.
- Users can vary the date range and status list to focus on completed/paid bookings.
- Results ordered by month ascending with a safety LIMIT 200.

### 试执行(真库 biz_reader 只读)—— 共 **13** 行,前 10 行:

| month | total_revenue_aud |
|---|---|
| 2025-08 | 3944023.83 |
| 2025-09 | 25438289.90 |
| 2025-10 | 28924499.04 |
| 2025-11 | 35222943.36 |
| 2025-12 | 32065558.07 |
| 2026-01 | 31262104.04 |
| 2026-02 | 21709415.09 |
| 2026-03 | 29324031.11 |
| 2026-04 | 10940769.54 |
| 2026-05 | 13186065.41 |

### 自修轨迹

一次通过,无自修。


---

## i09 — Stats: Top 10 customers by revenue (last 12 months)

> **brief(口径契约)**:Ranks customers by total booked revenue in AUD over a chosen period (commonly the last 12 months), excluding cancelled orders. Aggregation is the sum of order totals per customer; ties can be broken by most recent order date.

### 最终 SQL

```sql
SELECT
  c.id AS customer_id,
  c.name AS customer_name,
  SUM(o.total_amount) AS total_revenue_aud,
  MAX(o.order_date) AS most_recent_order_date
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.id
WHERE
  o.order_date >= '2025-08-23' AND o.status <> 'cancelled'
GROUP BY
  c.id,
  c.name
ORDER BY
  total_revenue_aud DESC,
  most_recent_order_date DESC
LIMIT 10
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:orders o JOIN customers c ON o.customer_id = c.id
- **度量口径**:
  - `SUM(o.total_amount)` — Total booked revenue in AUD per customer over the filtered period, excluding cancelled orders.
  - `MAX(o.order_date)` — Most recent order date per customer, used to break ties on revenue.
- **分组维度**:`c.id`, `c.name`

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `orders.order_date` | `>=` | `2025-08-23` | Default analysis window: last 12 months from 2026-08-23. |
| `orders.status` | `!=` | `cancelled` | Brief excludes cancelled orders from revenue. |

**口径落实**(应与 brief 一一对应):

- Ranks customers by total booked revenue (SUM of orders.total_amount) in AUD.
- Period is controlled by order_date with a default of the last 12 months.
- Cancelled orders are excluded via status != 'cancelled'.
- Grouping grain is customer; grouped by customer ID and name to avoid name collisions.
- Ties are broken by most recent order date using ORDER BY total_revenue_aud DESC, most_recent_order_date DESC.
- Top 10 enforced via LIMIT 10.

### 试执行(真库 biz_reader 只读)—— 共 **10** 行,前 10 行:

| customer_id | customer_name | total_revenue_aud | most_recent_order_date |
|---|---|---|---|
| 73 | Crestway Manufacturing Pty Ltd | 10306664.07 | 2026-08-06 |
| 56 | Meridian Aggregates Pty Ltd | 9517076.11 | 2026-08-17 |
| 26 | Crestway Food Processing Pty Ltd | 9448989.56 | 2026-08-21 |
| 61 | Harbour Packaging Pty Ltd | 7697896.46 | 2026-07-21 |
| 9 | Redgum Logistics Pty Ltd | 6609097.16 | 2026-08-09 |
| 42 | Crestway Cold Storage Pty Ltd | 6480855.78 | 2026-08-04 |
| 29 | Meridian Fabrication Pty Ltd | 6478864.85 | 2026-06-14 |
| 47 | Kestrel Dairy Co-op Pty Ltd | 6383115.13 | 2026-08-02 |
| 67 | Horizon Engineering Pty Ltd | 6350425.68 | 2026-06-15 |
| 35 | Summit Cold Storage Pty Ltd | 6198103.34 | 2026-05-25 |

### 自修轨迹

一次通过,无自修。


---

## i15 — Query: Stock movement history for a product at a warehouse

> **brief(口径契约)**:Shows the chronological ledger of movements for a chosen product at one warehouse over a date range, including movement date, type (inbound/outbound/adjustment), quantity, running balance after, and source reference. Users typically set the product, warehouse, and time window to investigate receipts, deliveries, or stocktakes. Useful for tracing discrepancies or confirming dispatches.

### 最终 SQL

```sql
SELECT
  p.sku AS product_sku,
  p.name AS product_name,
  sm.warehouse AS warehouse_name,
  sm.movement_date AS movement_date,
  sm.movement_type AS movement_type,
  sm.quantity AS quantity_moved,
  sm.balance_after AS balance_after,
  sm.reference_no AS source_reference,
  sm.id AS movement_id
FROM stock_movements AS sm
JOIN products AS p
  ON sm.product_id = p.id
WHERE
  p.sku LIKE '%ACC-CBL50%'
  AND sm.warehouse = 'Melbourne'
  AND sm.movement_date >= '2024-09-01'
  AND sm.movement_date <= '2026-08-23'
ORDER BY
  sm.movement_date ASC,
  sm.id ASC
LIMIT 50
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:stock_movements sm JOIN products p ON sm.product_id = p.id

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `products.sku` | `LIKE` | `%ACC-CBL50%` | Users identify the product by SKU/name; default to a concrete example SKU. |
| `stock_movements.warehouse` | `=` | `Melbourne` | Ledger is for a single warehouse; default to a concrete warehouse with data. |
| `stock_movements.movement_date` | `>=` | `2024-09-01` | Start of demo data to ensure matching rows while allowing users to narrow the window. |
| `stock_movements.movement_date` | `<=` | `2026-08-23` | End of available demo data (today) to bound the range. |

**口径落实**(应与 brief 一一对应):

- Chronological ledger implemented via ORDER BY movement_date ASC, id ASC.
- Includes movement date, type, quantity moved, running balance after, and source reference as required.
- Scoped to one chosen warehouse via equality filter; users can change the warehouse value.
- Product is chosen via human-facing SKU filter (can also be adjusted to name if needed).
- No currency conversions involved; quantities are unit counts.

### 试执行(真库 biz_reader 只读)—— 共 **26** 行,前 10 行:

| product_sku | product_name | warehouse_name | movement_date | movement_type | quantity_moved | balance_after | source_reference | movement_id |
|---|---|---|---|---|---|---|---|---|
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2024-09-05 | inbound | 531 | 531 | GRN-2024-00085 | 1128 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2024-10-20 | outbound | 152 | 379 | DO-2024-00094 | 1129 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-01-20 | outbound | 15 | 364 | DO-2025-00317 | 1130 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-03-03 | inbound | 882 | 1246 | GRN-2025-00215 | 1131 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-04-22 | outbound | 57 | 1189 | DO-2025-00318 | 1132 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-06-02 | inbound | 771 | 1960 | GRN-2025-00216 | 1133 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-06-26 | outbound | 1283 | 677 | DO-2025-00319 | 1134 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-07-24 | outbound | 423 | 254 | DO-2025-00320 | 1135 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-08-03 | inbound | 331 | 585 | GRN-2025-00217 | 1136 |
| ACC-CBL50 | DC Cable Kit 50m | Melbourne | 2025-08-24 | outbound | 351 | 234 | DO-2025-00321 | 1137 |

### 自修轨迹

一次通过,无自修。


---

## i16 — Stats: Monthly outbound units trend by warehouse

> **brief(口径契约)**:Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses.

### 最终 SQL

```sql
SELECT
  DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`,
  sm.warehouse AS `warehouse_name`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  DATE_FORMAT(sm.movement_date, '%Y-%m'),
  sm.warehouse
ORDER BY
  DATE_FORMAT(sm.movement_date, '%Y-%m') ASC
LIMIT 200
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:(单表,无 join)
- **度量口径**:
  - `SUM(sm.quantity)` — Total outbound units dispatched per month per warehouse.
- **分组维度**:`DATE_FORMAT(sm.movement_date, '%Y-%m')`, `sm.warehouse`

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `stock_movements.movement_date` | `BETWEEN` | `2025-08-23 AND 2026-08-23` | Default trend window: last 12 months up to 2026-08-23. |
| `stock_movements.movement_type` | `=` | `outbound` | Counts only units shipped out or transferred out, per brief. |
| `stock_movements.warehouse` | `IN` | `('Brisbane', 'Melbourne', 'Sydney')` | Default includes all warehouses; adjust list to include or exclude specific warehouses. |

**口径落实**(应与 brief 一一对应):

- Aggregates outbound movements only by filtering movement_type = 'outbound'.
- Groups by calendar year–month and warehouse as required.
- Sums quantity to measure units dispatched.
- Date range is user-variable via a BETWEEN filter with concrete defaults within data window.
- Warehouse inclusion/exclusion supported via IN list literals.
- Time-trend ordered ascending by month with a safety LIMIT 200.

### 试执行(真库 biz_reader 只读)—— 共 **39** 行,前 10 行:

| year_month | warehouse_name | outbound_units |
|---|---|---|
| 2025-08 | Brisbane | 23 |
| 2025-08 | Melbourne | 498 |
| 2025-08 | Sydney | 367 |
| 2025-09 | Brisbane | 1920 |
| 2025-09 | Melbourne | 1540 |
| 2025-09 | Sydney | 71 |
| 2025-10 | Brisbane | 1365 |
| 2025-10 | Melbourne | 1352 |
| 2025-10 | Sydney | 1201 |
| 2025-11 | Brisbane | 1238 |

### 自修轨迹

- 第 0 轮被打回,问题:
  - execution error on the live database: ProgrammingError: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near 'year_month, sm.warehouse AS warehouse_name, SUM(sm.quantity) AS outbound_units F' at line 1")


---

## i18 — Stats: Top products by outbound units (last 90 days)

> **brief(口径契约)**:Ranks products by shipment volume over a recent period. Groups by product and sums quantity where movement_type is outbound within the chosen window (e.g., last 90 days), then orders descending to return the top N products; this reflects units shipped to customers. Users vary the lookback window and optionally limit to certain warehouses.

### 最终 SQL

```sql
SELECT
  p.id AS product_id,
  p.sku AS product_sku,
  p.name AS product_name,
  SUM(sm.quantity) AS total_outbound_units
FROM stock_movements AS sm
JOIN products AS p
  ON sm.product_id = p.id
WHERE
  sm.movement_date >= '2026-05-25'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  p.id,
  p.sku,
  p.name
ORDER BY
  total_outbound_units DESC
LIMIT 10
```

### 设计说明(LLM 自声明,请对照 brief 审)

- **join 路径**:stock_movements sm JOIN products p ON sm.product_id = p.id
- **度量口径**:
  - `SUM(sm.quantity)` — Total units shipped outbound per product within the window.
- **分组维度**:`p.id`, `p.sku`, `p.name`

**WHERE 默认条件**(运行时改写只能改这些条件的值/启停,不能新增):

| 列 | 操作符 | 默认值 | 业务理由 |
|---|---|---|---|
| `stock_movements.movement_date` | `>=` | `2026-05-25` | Lookback window defaulted to last 90 days ending 2026-08-23. |
| `stock_movements.movement_type` | `=` | `outbound` | Only count shipments to customers; excludes inbound and adjustments. |
| `stock_movements.warehouse` | `IN` | `('Brisbane','Melbourne','Sydney')` | Enable optional restriction to specific warehouses; default includes all known warehouses. |

**口径落实**(应与 brief 一一对应):

- Ranks products by summed outbound quantity within the chosen window.
- Groups by product (id with sku and name) to avoid merging distinct IDs sharing a name.
- Filters movement_type to outbound to reflect units shipped to customers.
- Implements a variable lookback window via movement_date >= literal; default is last 90 days.
- Orders by total_outbound_units descending and limits to top N (default 10).

### 试执行(真库 biz_reader 只读)—— 共 **10** 行,前 10 行:

| product_id | product_sku | product_name | total_outbound_units |
|---|---|---|---|
| 18 | ACC-GATE | Monitoring Gateway G2 | 1623 |
| 19 | ACC-METER | Smart Energy Meter 3-Phase | 1482 |
| 16 | ACC-RACK | HC Series Mounting Rack Kit | 1395 |
| 20 | ACC-COOL | HC Series HVAC Cooling Module | 1341 |
| 17 | ACC-CBL50 | DC Cable Kit 50m | 1123 |
| 8 | INV-25K | SolarWave INV-25K String Inverter 25kW | 509 |
| 12 | INV-333K | SolarWave INV-333K Central Inverter 333kW | 228 |
| 10 | INV-110K | SolarWave INV-110K String Inverter 110kW | 226 |
| 9 | INV-50K | SolarWave INV-50K String Inverter 50kW | 191 |
| 14 | EMS-PRO | GridMind EMS Pro Licence | 173 |

### 自修轨迹

一次通过,无自修。


---

## 附:生成机制全披露(本节由代码常量渲染,与实际执行零漂移)

### ① 输入:两条消息

**system prompt(分型两套,共用铁律 + 各自策略与手写样例)**

<details><summary>system prompt — query 型(点开看全文)</summary>

```text
You are a senior analytics engineer writing a VERIFIED SQL TEMPLATE for MySQL 8.

A template is a runnable SELECT with sensible LITERAL default values. At runtime a
constrained rewriter may only: change WHERE literal values, drop output columns, or
drop GROUP BY columns. It can NEVER add tables, columns or conditions. So the template
must already contain every column and condition a user is likely to vary, with good defaults.

Authoritative inputs:
- The intent (one_liner + brief). The brief is the business-caliber contract: implement
  EVERY caliber it states (exclusions, currency, grouping grain, ranking rule).
- The schema subset: tables with column descriptions and enum meanings, plus relations.
  Use ONLY these tables. Join ONLY along the given relations.

Iron rules for the SQL:
1. Exactly one SELECT statement. No CTEs, no subqueries, no UNION, no comments.
2. Every WHERE condition is `column <operator> literal`, operator in: = != > >= < <=
   BETWEEN IN LIKE. Combine conditions with AND only.
3. Time defaults are ABSOLUTE date literals (today is 2026-08-23): e.g. "last 12 months"
   becomes `order_date >= '{today minus 12 months}'`. Never CURDATE()/NOW() arithmetic.
4. Every projected column has a readable snake_case English alias (e.g. AS customer_name).
   No SELECT *. Qualify every column with its table alias.
5. Always include a LIMIT (see the type strategy for the value).
6. When the brief says users identify things by name / SKU / order number, filter on that
   human-facing column (LIKE or =), not on a surrogate id.
7. English only.
8. At most ONE WHERE condition per business concept. Never redundant alternates such as
   both `status != 'x'` and `status IN (...)` on the same column — pick the single form
   that best matches the brief.
9. Identity filters (customer name, order number, SKU...): default to a CONCRETE example
   value taken from sample_values, never a match-all placeholder like LIKE '%'. The
   template's default run must read like a real answer to the intent.
10. When ranking or grouping by an entity, GROUP BY its primary key together with the
    displayed name, so distinct entities sharing a name are not merged.

Also return a `design` object that makes your decisions reviewable:
- join_path: the FROM/JOIN chain as plain text, or null for a single table.
- measures: for stats, each aggregate expression and its business meaning; null for query.
- group_by_dims: the GROUP BY expressions; null for query.
- default_filters: EVERY WHERE condition, with a one-line business reason (why) and the
  default value as a string.
- caliber_notes: one note per caliber stated in the brief, saying how the SQL implements it.

Type strategy — QUERY (detail rows, no aggregation):
- No GROUP BY and no aggregate functions anywhere.
- ORDER BY the most natural recency/importance column (usually date DESC), then LIMIT 50.

Worked example (neutral schema, style reference only):
intent: "Query: Recent payments for a specific store" / brief: users vary the store (by
name), a date range, and payment methods; sorted by most recent.
{
 "sql": "SELECT s.name AS store_name, p.paid_at AS paid_at, p.method AS payment_method, p.amount AS amount_aud FROM payments p JOIN stores s ON p.store_id = s.id WHERE s.name LIKE '%Acme%' AND p.paid_at >= '2026-05-25' AND p.method IN ('card', 'cash') ORDER BY p.paid_at DESC LIMIT 50",
 "design": {"join_path": "payments p JOIN stores s ON p.store_id = s.id",
            "measures": null, "group_by_dims": null,
            "default_filters": [
              {"column": "stores.name", "operator": "LIKE", "value": "%Acme%",
               "why": "Users identify the store by name, not by id."},
              {"column": "payments.paid_at", "operator": ">=", "value": "2026-05-25",
               "why": "Default to the last 90 days of activity."},
              {"column": "payments.method", "operator": "IN", "value": "('card', 'cash')",
               "why": "Both common methods included by default; users may narrow."}],
            "caliber_notes": ["Amounts are shown as stored (AUD), no conversion."]}
}
```
</details>

<details><summary>system prompt — stats 型(点开看全文)</summary>

```text
You are a senior analytics engineer writing a VERIFIED SQL TEMPLATE for MySQL 8.

A template is a runnable SELECT with sensible LITERAL default values. At runtime a
constrained rewriter may only: change WHERE literal values, drop output columns, or
drop GROUP BY columns. It can NEVER add tables, columns or conditions. So the template
must already contain every column and condition a user is likely to vary, with good defaults.

Authoritative inputs:
- The intent (one_liner + brief). The brief is the business-caliber contract: implement
  EVERY caliber it states (exclusions, currency, grouping grain, ranking rule).
- The schema subset: tables with column descriptions and enum meanings, plus relations.
  Use ONLY these tables. Join ONLY along the given relations.

Iron rules for the SQL:
1. Exactly one SELECT statement. No CTEs, no subqueries, no UNION, no comments.
2. Every WHERE condition is `column <operator> literal`, operator in: = != > >= < <=
   BETWEEN IN LIKE. Combine conditions with AND only.
3. Time defaults are ABSOLUTE date literals (today is 2026-08-23): e.g. "last 12 months"
   becomes `order_date >= '{today minus 12 months}'`. Never CURDATE()/NOW() arithmetic.
4. Every projected column has a readable snake_case English alias (e.g. AS customer_name).
   No SELECT *. Qualify every column with its table alias.
5. Always include a LIMIT (see the type strategy for the value).
6. When the brief says users identify things by name / SKU / order number, filter on that
   human-facing column (LIKE or =), not on a surrogate id.
7. English only.
8. At most ONE WHERE condition per business concept. Never redundant alternates such as
   both `status != 'x'` and `status IN (...)` on the same column — pick the single form
   that best matches the brief.
9. Identity filters (customer name, order number, SKU...): default to a CONCRETE example
   value taken from sample_values, never a match-all placeholder like LIKE '%'. The
   template's default run must read like a real answer to the intent.
10. When ranking or grouping by an entity, GROUP BY its primary key together with the
    displayed name, so distinct entities sharing a name are not merged.

Also return a `design` object that makes your decisions reviewable:
- join_path: the FROM/JOIN chain as plain text, or null for a single table.
- measures: for stats, each aggregate expression and its business meaning; null for query.
- group_by_dims: the GROUP BY expressions; null for query.
- default_filters: EVERY WHERE condition, with a one-line business reason (why) and the
  default value as a string.
- caliber_notes: one note per caliber stated in the brief, saying how the SQL implements it.

Type strategy — STATS (aggregation, GROUP BY required):
- GROUP BY exactly the dimensions the brief implies. Monthly grain uses
  DATE_FORMAT(date_col, '%Y-%m').
- Aggregate at the correct grain: beware fan-out joins double-counting a parent measure.
- Ranking intents: ORDER BY the main aggregate DESC, LIMIT to the brief's top-N.
- Time-trend intents: ORDER BY the period ascending, LIMIT 200 as a safety cap.

Worked example (neutral schema, style reference only):
intent: "Stats: Monthly paid amount trend by store" / brief: sums payment amounts per
calendar month and store, excluding voided payments; users vary the date range.
{
 "sql": "SELECT DATE_FORMAT(p.paid_at, '%Y-%m') AS month, s.name AS store_name, SUM(p.amount) AS total_paid_aud FROM payments p JOIN stores s ON p.store_id = s.id WHERE p.paid_at >= '2025-08-23' AND p.status != 'voided' GROUP BY DATE_FORMAT(p.paid_at, '%Y-%m'), s.name ORDER BY month ASC LIMIT 200",
 "design": {"join_path": "payments p JOIN stores s ON p.store_id = s.id",
            "measures": [{"expr": "SUM(p.amount)",
                          "meaning": "Total paid amount in AUD per month per store."}],
            "group_by_dims": ["DATE_FORMAT(p.paid_at, '%Y-%m')", "s.name"],
            "default_filters": [
              {"column": "payments.paid_at", "operator": ">=", "value": "2025-08-23",
               "why": "Default trend window: last 12 months."},
              {"column": "payments.status", "operator": "!=", "value": "voided",
               "why": "Brief excludes voided payments from the caliber."}],
            "caliber_notes": ["Voided payments excluded per brief.",
                              "Grain is calendar month by payment date."]}
}
```
</details>

**user payload**:`business_context`(业务背景)+ `intent`(id/type/bucket/one_liner/brief 原文,brief 即口径契约)+ `schema_subset`(语义层按 intent.tables 裁剪:列描述/枚举含义/关系)+ `notes_for_defaults`(数据范围提示)。

<details><summary>实际样例:i07 的 user payload 全文(单表,最短)</summary>

```json
{
 "business_context": "Clenergy is an Australian manufacturer of solar PV mounting systems. This database covers its sales side: products (mounting kits, inverters, energy-management gear, accessories), customers, sales reps, orders with line items, and warehouse inventory with a stock-movement ledger. Amounts are in AUD.",
 "intent": {
  "id": "i07",
  "type": "stats",
  "bucket": "time_stats",
  "one_liner": "Stats: Monthly revenue trend (excluding cancelled)",
  "brief": "Aggregates total booked revenue per calendar month based on order date, summing order totals in AUD and excluding orders with status cancelled. Users vary the date range and may filter by status to focus on completed/paid bookings."
 },
 "schema_subset": {
  "tables": [
   {
    "name": "orders",
    "description": "One row represents a single customer sales order placed with Clenergy. The table tracks who the customer and sales rep are, the order date and status, and the total order value in AUD; detailed products are stored in order_items.",
    "columns": [
     {
      "name": "id",
      "display_name": "Order ID",
      "description": "System-generated primary key for the order. Used to join to order_items.order_id.",
      "type": "int unsigned",
      "enum_values": null
     },
     {
      "name": "order_no",
      "display_name": "Order Number",
      "description": "Business order number, e.g. SO-2025-00123",
      "type": "varchar(20)",
      "enum_values": null
     },
     {
      "name": "customer_id",
      "display_name": "Customer ID",
      "description": "References customers.id, linking the order to the purchasing customer. Use to join and retrieve customer details such as name, state, and industry.",
      "type": "int unsigned",
      "enum_values": null
     },
     {
      "name": "sales_rep_id",
      "display_name": "Sales Rep ID",
      "description": "References sales_reps.id, indicating the sales representative responsible for the order. Use to join for rep name, team, and territory details.",
      "type": "int unsigned",
      "enum_values": null
     },
     {
      "name": "order_date",
      "display_name": "Order Date",
      "description": "Calendar date the order was created, stored as YYYY-MM-DD (day-level granularity). Used for booking and time-based reporting.",
      "type": "date",
      "enum_values": null
     },
     {
      "name": "status",
      "display_name": "Order Status",
      "description": "Current lifecycle state of the order. Used to track processing, fulfillment, and closure.",
      "type": "varchar(16)",
      "enum_values": [
       {
        "value": "cancelled",
        "meaning": "Order was voided and will not be fulfilled or invoiced further."
       },
       {
        "value": "completed",
        "meaning": "Order has been fully fulfilled and closed out."
       },
       {
        "value": "paid",
        "meaning": "Payment has been received for the order."
       },
       {
        "value": "pending",
        "meaning": "Order has been created and is awaiting further processing (e.g., payment or fulfillment)."
       },
       {
        "value": "shipped",
        "meaning": "Goods have been dispatched to the customer."
       }
      ]
     },
     {
      "name": "total_amount",
      "display_name": "Order Total",
      "description": "Order total in AUD, equals the sum of its line amounts",
      "type": "decimal(14,2)",
      "enum_values": null
     }
    ]
   }
  ],
  "relations": []
 },
 "sample_values": {
  "orders": {
   "id": [
    "1",
    "2",
    "3",
    "4",
    "5"
   ],
   "order_no": [
    "SO-2024-00001",
    "SO-2024-00002",
    "SO-2024-00003",
    "SO-2024-00004",
    "SO-2024-00005"
   ],
   "customer_id": [
    "1",
    "2",
    "3",
    "4",
    "5"
   ],
   "sales_rep_id": [
    "1",
    "2",
    "3",
    "4",
    "5"
   ],
   "order_date": [
    "2024-09-01",
    "2024-09-02",
    "2024-09-03",
    "2024-09-04",
    "2024-09-05"
   ],
   "status": [
    "cancelled",
    "completed",
    "paid",
    "pending",
    "shipped"
   ],
   "total_amount": [
    "734.62",
    "987.24",
    "1744.45",
    "2268.88",
    "2499.91"
   ]
  }
 },
 "notes_for_defaults": "The demo database contains data from 2024-09-01 to 2026-08-23. Pick default filter values that are guaranteed to match rows; for identity filters pick a concrete value from sample_values."
}
```
</details>

### ② 输出契约(json_schema 强制)

`sql`(单条可运行 SELECT)+ `design`(join_path / measures / group_by_dims / default_filters(每条 WHERE 的业务理由)/ caliber_notes(逐条口径落实声明))。design 不进模板、只进本报告 —— 静默错答(SQL 能跑但口径错)只能靠人审口径,这是审的抓手。

```json
{
 "name": "sql_template",
 "schema": {
  "type": "object",
  "required": [
   "sql",
   "design"
  ],
  "properties": {
   "sql": {
    "type": "string"
   },
   "design": {
    "type": "object",
    "required": [
     "join_path",
     "measures",
     "group_by_dims",
     "default_filters",
     "caliber_notes"
    ],
    "properties": {
     "join_path": {
      "type": [
       "string",
       "null"
      ]
     },
     "measures": {
      "type": [
       "array",
       "null"
      ],
      "items": {
       "type": "object",
       "required": [
        "expr",
        "meaning"
       ],
       "properties": {
        "expr": {
         "type": "string"
        },
        "meaning": {
         "type": "string"
        }
       }
      }
     },
     "group_by_dims": {
      "type": [
       "array",
       "null"
      ],
      "items": {
       "type": "string"
      }
     },
     "default_filters": {
      "type": "array",
      "items": {
       "type": "object",
       "required": [
        "column",
        "operator",
        "value",
        "why"
       ],
       "properties": {
        "column": {
         "type": "string"
        },
        "operator": {
         "type": "string"
        },
        "value": {
         "type": "string"
        },
        "why": {
         "type": "string"
        }
       }
      }
     },
     "caliber_notes": {
      "type": "array",
      "items": {
       "type": "string"
      }
     }
    }
   }
  }
 }
}
```

### ③ 确定性静态校验(sqlglot AST,非正则)

- 单条语句且必须是 SELECT;禁 CTE / 子查询 / UNION
- 禁相对时间函数(CURDATE/NOW/SYSDATE/CURRENT_DATE...)—— 时间默认值必须绝对字面量
- 引用的表 ⊆ intent.tables;每个列经别名解析后必须存在于语义层对应表(防幻觉列)
- 禁 SELECT *;每个输出列必须带 snake_case 别名(可读列名)
- WHERE 仅 AND 连接;每个条件必须是 列 op 字面量,op ∈ {=, !=, >, >=, <, <=, BETWEEN, IN, LIKE}(B5 拆参数的前提)
- query 型:禁 GROUP BY / 聚合函数 / HAVING,必有 ORDER BY 与 LIMIT
- stats 型:必有 GROUP BY 与 ORDER BY 与 LIMIT
- LIMIT 必须存在且 1..500
- SQL 全英文(无 CJK 字符)

### ④ 真库试执行与自修回灌

- 静态校验全过才试执行(只读账号);**执行报错或返回 0 行都算失败**,问题清单回灌重生成,最多 2 轮;
- 回灌消息模板(verbatim):

```text
Your previous answer failed these checks:
{problems}

Return the corrected FULL JSON object (sql + design), fixing every issue and keeping design consistent with the corrected SQL.
```
- 试执行走 `db.query(sql)`(args=None,避免 pymysql 对 `DATE_FORMAT('%Y-%m')` 字面 % 的误格式化)。
