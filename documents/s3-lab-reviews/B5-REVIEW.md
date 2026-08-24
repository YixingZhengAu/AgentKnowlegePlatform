# B5 评审报告:模板参数包(三区解析 + AI 预填)

> 生成于 2026-08-23。输入 = B4 定稿模板(`out/templates/`,冻结)。解析为**纯确定性代码**(sqlglot AST 拆三区,LLM 不碰结构);AI 只预填 `business_name`(表单上的人话标签)与 `hint`(给 B6 运行时改写器的取值说明书)。

**人审三问**:

1. **business_name 是否说人话** —— 它将来就是前端参数卡片的标签;

2. **hint 是否足以指导改写器取值** —— 时间参数有没有格式与窗口;枚举参数有没有全部取值;默认启用/禁用语义对不对(重点:i02 `is_active` 评审时已放开为默认不过滤,hint 必须写清'用户要 active only 时才收窄到 1');

3. **三区点数与 SQL 对照** —— 每条模板的 filters/outputs/groupbys 是否一个不丢一个不多(下表已与人工点数核对)。

**定稿动作**:回复采纳/修改意见;认可后打 `finalized_at` 复制到 `out/published/`,即为'保存即发布'的发布态,B6 输入冻结。


## 总览(三区点数已对人工核数)

| 意图 | 类型 | one-liner | filters | outputs | groupbys | 预填自修轮数 |
|---|---|---|---|---|---|---|
| i01 | **查询** Query | Query: Recent orders for a specific customer | 3 | 5 | 0 | 0 |
| i02 | **查询** Query | Query: Line items for an order number | 2 | 6 | 0 | 0 |
| i07 | **统计** Stats | Stats: Monthly revenue trend (excluding cancelled) | 2 | 2 | 1 | 0 |
| i09 | **统计** Stats | Stats: Top 10 customers by revenue (last 12 months) | 2 | 4 | 2 | 0 |
| i15 | **查询** Query | Query: Stock movement history for a product at a warehouse | 4 | 9 | 0 | 0 |
| i16 | **统计** Stats | Stats: Monthly outbound units trend by warehouse | 3 | 3 | 2 | 0 |
| i18 | **统计** Stats | Stats: Top products by outbound units (last 90 days) | 3 | 4 | 3 | 0 |

---

## i01 · **查询** Query

**Query: Recent orders for a specific customer**

> Returns detailed orders for a chosen customer, including order number, date, status, and order total. Users typically vary the customer (by name or ID), a date range, and statuses to include or exclude (e.g., exclude cancelled). Results can be sorted by most recent or highest value.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_name` | `customers.name` | `LIKE` | `"%Bluegum Beverages Pty Ltd%"` | string/scalar | Customer name | Map any customer name mentioned by the user to this filter. This is a partial, case-insensitive contains match. Replace the default value with the exact name fragment the user gives, keeping the surrounding % wildcards (e.g., user says “Acme” -> set to %Acme%). Only name-based filtering is supported in this template; if the user supplies a customer ID without a name, leave the default or disable only if they clearly want all customers. DEFAULT: keep %Bluegum Beverages Pty Ltd% when the user does not specify a customer. DISABLE: only if the user explicitly asks for all customers or to remove the customer filter. |
| `f_order_date` | `orders.order_date` | `>=` | `"2025-08-23"` | date/scalar | Start order date | Maps phrases like “since 2026-01-01”, “from Jan 1, 2026”, “last 90 days”, “this year”, “last month” to the start date boundary. Value format must be YYYY-MM-DD. Resolve any relative dates to absolute dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; clamp or choose a start date within this window. This filter is >= start date only; no end date can be added. DEFAULT: keep 2025-08-23 if the user does not mention date. DISABLE: only if the user asks for all dates/no date filter (which will return all available dates in the data window). |
| `f_status` | `orders.status` | `IN` | `["completed", "paid", "pending", "shipped"]` | enum/list | Order statuses | Map user intent about which statuses to include/exclude. Allowed values ONLY: cancelled (voided), completed (fulfilled/closed), paid (payment received), pending (awaiting processing), shipped (dispatched). Accept phrasings like “only completed”, “exclude cancelled”, “include cancelled too”, “pending and shipped”, “any status”. Set the IN list to exactly the requested subset; reject any value outside the allowed list (do not guess). DEFAULT: keep ['completed','paid','pending','shipped'] if user does not mention status. DISABLE: only if the user explicitly wants all/any statuses. |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_customer_name` | `c.name` | `customer_name` | Customer name | Output column showing the customer’s legal or trading name. Keep by default. Drop only if the user asks for fewer columns and does not need customer name (e.g., “just order numbers and totals”). |
| `o_order_number` | `o.order_no` | `order_number` | Order number | Output column showing the business order number (e.g., SO-2025-00123). Keep by default. Drop only if the user requests a narrower output that excludes order numbers. |
| `o_order_date` | `o.order_date` | `order_date` | Order date | Output column showing the order creation date (YYYY-MM-DD). Keep by default. Drop only if the user asks to omit dates. |
| `o_order_status` | `o.status` | `order_status` | Order status | Output column showing the current lifecycle status of the order. Keep by default. Drop only if the user asks to omit statuses. |
| `o_order_total_aud` | `o.total_amount` | `order_total_aud` | Order total (AUD) | Output column showing the order total amount in AUD. Keep by default. Drop only if the user requests fewer columns and does not need totals. |

---

## i02 · **查询** Query

**Query: Line items for an order number**

> Lists all product lines on a given order: product SKU/name, quantity, unit sell price, and line amount in AUD. Users provide an order number and may also filter to active products only for validation.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_order_no` | `orders.order_no` | `=` | `"SO-2024-00001"` | string/scalar | Order number | Filter: Maps from phrases like “order number,” “order no,” “SO number,” “sales order,” or a value like SO-2025-00123. Take exactly one order number as a single string, preserving the SO prefix, hyphens, and zero padding (e.g., SO-2025-00123). Do not split or expand to multiple orders. DEFAULT: Keep SO-2024-00001 when the user does not supply an order number. DISABLE: Only if the user explicitly asks for all orders or to remove the order-number filter; otherwise never disable. |
| `f_is_active` | `products.is_active` | `IN` | `[0, 1]` | enum/list | Product status | Filter: Maps from phrases like “active only,” “only active products,” “inactive only,” “discontinued,” “retired,” or “all statuses/both.” Value is a list of enums; allowed values only: 1 = Product is active and available for sale; 0 = Product is inactive/not for sale. Accept lists [1], [0], or [0,1] only; reject anything else. DEFAULT: Keep [0,1] (both) if the user does not specify. DISABLE: Only if the user explicitly asks to remove the status filter (note this is effectively the same as [0,1] in most cases). |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_order_number` | `o.order_no` | `order_number` | Order number | Output: Shows the business order number for each line. Keep unless the user asks to omit it; drop only if they want fewer columns and the order is already known from context. |
| `o_product_sku` | `p.sku` | `product_sku` | Product SKU | Output: Shows the product SKU for each line. Keep by default; drop only if the user explicitly wants fewer columns (e.g., name only). |
| `o_product_name` | `p.name` | `product_name` | Product name | Output: Shows the human-readable product name. Keep by default; drop only if the user asks for fewer columns (e.g., SKU only). |
| `o_quantity` | `oi.quantity` | `quantity` | Quantity | Output: Units ordered on the line (whole number). Keep by default; drop only if the user asks to exclude quantities. |
| `o_unit_sell_price_aud` | `oi.unit_price` | `unit_sell_price_aud` | Unit price (AUD) | Output: Actual sell price per unit in AUD. Keep by default; drop only if the user wants a narrower view without pricing. |
| `o_line_amount_aud` | `oi.line_amount` | `line_amount_aud` | Line amount (AUD) | Output: Extended line total in AUD (typically quantity × unit price). Keep by default; drop only if the user requests fewer columns or no totals. |

---

## i07 · **统计** Stats

**Stats: Monthly revenue trend (excluding cancelled)**

> Aggregates total booked revenue per calendar month based on order date, summing order totals in AUD and excluding orders with status cancelled. Users vary the date range and may filter by status to focus on completed/paid bookings.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_order_date` | `orders.order_date` | `>=` | `"2025-08-23"` | date/scalar | Order date from | Filter: Maps phrases like "from", "since", "starting", "after" to this lower bound on order date. Accept a single date in format YYYY-MM-DD. Resolve relative dates (e.g., "last month", "last 90 days", "since Jan 2026") to absolute dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; if a parsed date falls outside, clamp to this window. DEFAULT/DISABLE: If the user does not mention a start date, keep the template default 2025-08-23. You may disable this condition only if the user explicitly asks for "all dates", "no start date", or "from the beginning". |
| `f_status` | `orders.status` | `!=` | `"cancelled"` | enum/scalar | Exclude order status | Filter (enum exclusion): This parameter excludes exactly one status value from results. Map user intent like "exclude X", "hide X", or "without X" to set X here. Allowed values only (must match exactly): cancelled (exclude cancelled orders), completed (exclude completed orders), paid (exclude paid orders), pending (exclude pending orders), shipped (exclude shipped orders). Values outside this list must not be used. Note: This is NOT an include-only filter; it cannot restrict results to only one status. DEFAULT/DISABLE: If the user says nothing about status, keep the default exclude cancelled. Disable this filter only when the user asks to include cancelled orders or wants "all statuses" with no exclusions. |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_month` | `DATE_FORMAT(o.order_date, '%Y-%m')` | `month` | Month | Output: Calendar month of the order date, formatted as YYYY-MM (e.g., 2026-03). Keep this column for any monthly trend or breakdown. Drop it only if the user explicitly asks for a single overall total without monthly detail. |
| `o_total_revenue_aud` | `SUM(o.total_amount)` | `total_revenue_aud` | Total revenue (AUD) | Output: Sum of order totals in AUD within each month (or overall if month grouping is dropped). This reflects booked revenue for included statuses and dates. Keep unless the user explicitly requests to see only the month labels without amounts. |

### 分组参数(GROUP BY)

| param_id | 表达式 | 回链输出别名 | business_name | hint |
|---|---|---|---|---|
| `g_month` | `DATE_FORMAT(o.order_date, '%Y-%m')` | `month` | Group by month | Group by: Aggregates results per calendar month (YYYY-MM). Dropping this makes the numbers roll up to a single total over the selected date range. Only drop if the user asks for an overall/grand total with no monthly breakdown or for less detail than monthly. |

---

## i09 · **统计** Stats

**Stats: Top 10 customers by revenue (last 12 months)**

> Ranks customers by total booked revenue in AUD over a chosen period (commonly the last 12 months), excluding cancelled orders. Aggregation is the sum of order totals per customer; ties can be broken by most recent order date.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_order_date` | `orders.order_date` | `>=` | `"2025-08-23"` | date/scalar | Order date on/after | Filter mapping: user phrases that set the earliest order date to include, e.g., "last 12 months", "since 2025-05-01", "from Jan 1 2026", "year to date", "this year", "after 2025-08-01". Value format must be a single date YYYY-MM-DD. Resolve any relative date phrases to absolute dates anchored at 2026-08-23. Examples: last 12 months -> 2025-08-23; year to date/this year -> 2026-01-01; since 2025-05-01 -> 2025-05-01; after 2025-08-01 -> 2025-08-02. Valid data window is 2024-09-01 to 2026-08-23; clamp to this range if needed. DEFAULT/DISABLE: If the user does not mention a time filter, keep the default 2025-08-23 (matches the brief of last 12 months). Disable this filter only if the user explicitly asks for all-time/no date filter or a period that starts before 2024-09-01 (then disable only if they clearly want no lower bound). |
| `f_status` | `orders.status` | `!=` | `"cancelled"` | enum/scalar | Exclude order status | This filter excludes exactly one order status via !=. Map user intent like "exclude cancelled" (default), "exclude shipped", etc., by setting the value to that single status. Allowed values (must use one verbatim; reject anything else): cancelled (voided order), completed (fully fulfilled), paid (payment received), pending (awaiting processing), shipped (dispatched). DEFAULT/DISABLE: If the user does not mention status logic, keep the default exclusion of cancelled. Disable this filter only if the user explicitly wants all statuses included, including cancelled (e.g., "include cancelled" or "don’t exclude any status"). Note: You cannot switch this to an inclusion-only filter (e.g., "only completed")—that is not supported by this template. |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_customer_id` | `c.id` | `customer_id` | Customer ID | Output: the internal unique customer identifier. Keep unless the user asks to hide IDs or wants a higher-level rollup without per-customer detail. Drop only if the user requests no customer-level detail or explicitly says to omit IDs; if dropped, also drop the matching group by (g_customer_id) to keep aggregation consistent. |
| `o_customer_name` | `c.name` | `customer_name` | Customer name | Output: the customer’s legal/trading name. Keep by default to identify each ranked customer. Drop only if the user asks for no customer breakdown or explicitly asks to omit names; if dropped, also drop the matching group by (g_customer_name). |
| `o_total_revenue_aud` | `SUM(o.total_amount)` | `total_revenue_aud` | Total revenue (AUD) | Output: sum of order totals in AUD per customer over the filtered period, excluding the status that is filtered out. This is the ranking metric. Keep unless the user explicitly asks for a different, narrower field list (rare); typically must be retained for a top-customer ranking. |
| `o_most_recent_order_date` | `MAX(o.order_date)` | `most_recent_order_date` | Most recent order date | Output: the latest order date per customer within the filtered period; used as a tie-breaker in ordering. Keep by default; drop only if the user wants a minimal output without dates. |

### 分组参数(GROUP BY)

| param_id | 表达式 | 回链输出别名 | business_name | hint |
|---|---|---|---|---|
| `g_customer_id` | `c.id` | `customer_id` | Group by customer ID | Dimension: groups results by unique customer. Dropping this aggregates customers together by whatever group-bys remain. Only drop if the user asks to: (a) hide IDs but still group by name (then drop this group-by together with the ID output), or (b) remove all customer breakdown (then drop both customer group-bys to get an overall total). |
| `g_customer_name` | `c.name` | `customer_name` | Group by customer name | Dimension: groups results by customer name. Dropping this rolls up multiple customers that share a name or, if both customer group-bys are dropped, produces a single overall total. Only drop if the user asks for less detail (e.g., no names shown) or for an overall total without per-customer rows; ensure you also drop the corresponding output when removing this grouping. |

---

## i15 · **查询** Query

**Query: Stock movement history for a product at a warehouse**

> Shows the chronological ledger of movements for a chosen product at one warehouse over a date range, including movement date, type (inbound/outbound/adjustment), quantity, running balance after, and source reference. Users typically set the product, warehouse, and time window to investigate receipts, deliveries, or stocktakes. Useful for tracing discrepancies or confirming dispatches.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_sku` | `products.sku` | `LIKE` | `"%ACC-CBL50%"` | string/scalar | Product SKU | Filter. Maps from user mentions of the product code/SKU such as “SKU”, “product code”, or fragments like “ACC-CBL50”, “starts with ACC-”, or “contains CBL50”. This is a partial, case-insensitive contains match. Replace the default with the user’s SKU fragment while keeping the surrounding % wildcards (e.g., %CBL50%). Do not attempt to use product names here. DEFAULT: keep %ACC-CBL50% if the user does not specify a SKU. DISABLE: do not disable this filter; a specific product is required for this ledger. |
| `f_warehouse` | `stock_movements.warehouse` | `=` | `"Melbourne"` | enum/scalar | Warehouse | Filter. Maps from phrases like “at/in the Melbourne warehouse”, “Sydney warehouse”, or “Brisbane”. Allowed values only: Brisbane (Brisbane warehouse), Melbourne (Melbourne warehouse), Sydney (Sydney warehouse). Reject any value outside this list; do not guess. DEFAULT: keep Melbourne if the user does not mention a warehouse. DISABLE: only disable if the user explicitly asks for all/any warehouses; otherwise keep it enabled for a single-warehouse ledger. |
| `f_movement_date_ge` | `stock_movements.movement_date` | `>=` | `"2024-09-01"` | date/scalar | From date | Filter. Lower bound of movement date. Accept YYYY-MM-DD. Resolve relative phrases (e.g., “since Jan 2025”, “from last month”, “after 2025-03-10”, “on 2025-04-10”, “July 2025”) to absolute dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; clamp earlier values up to 2024-09-01 if needed. For “on <date>”, set both lower and upper to that date. For “<month/year>”, set to the first day of that month. DEFAULT: keep 2024-09-01 if the user does not specify a start. DISABLE: disable this lower bound only if the user asks for “before <date>”, “up to <date>”, or “all dates” (in which case rely on the upper bound/window). |
| `f_movement_date_le` | `stock_movements.movement_date` | `<=` | `"2026-08-23"` | date/scalar | To date | Filter. Upper bound of movement date. Accept YYYY-MM-DD. Resolve relative phrases (e.g., “until 2025-06-30”, “before April 2025”, “this month”, “through last week”, “on 2025-04-10”, “July 2025”) to absolute dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; clamp later values down to 2026-08-23 if needed. For “on <date>”, set both lower and upper to that date. For “<month/year>”, set to the last day of that month (bounded by the window). DEFAULT: keep 2026-08-23 if the user does not specify an end. DISABLE: disable this upper bound only if the user asks for “since/from <date>”, “after <date>”, or “all dates” (in which case rely on the lower bound/window). |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_product_sku` | `p.sku` | `product_sku` | SKU | Output. Shows the product’s SKU on each movement row. Keep unless the user asks to hide product identifiers; safe to drop for a narrower answer. |
| `o_product_name` | `p.name` | `product_name` | Product name | Output. Human-readable product name associated with the SKU. Keep by default; drop only if the user requests fewer columns or identifiers. |
| `o_warehouse_name` | `sm.warehouse` | `warehouse_name` | Warehouse name | Output. Warehouse (city) where the movement occurred. Keep by default to confirm location; drop only if the user wants fewer columns and the warehouse is already fixed by the filter. |
| `o_movement_date` | `sm.movement_date` | `movement_date` | Movement date | Output. Calendar date of each stock movement in the ledger. Keep unless the user explicitly wants to hide dates. |
| `o_movement_type` | `sm.movement_type` | `movement_type` | Movement type | Output. Whether the movement is inbound, outbound, or an adjustment. Keep by default; drop only on explicit request for fewer details. |
| `o_quantity_moved` | `sm.quantity` | `quantity_moved` | Quantity moved | Output. Units moved in the transaction. Keep by default; drop only if the user asks for a slimmer view without quantities. |
| `o_balance_after` | `sm.balance_after` | `balance_after` | Balance after | Output. On-hand quantity immediately after the movement (running balance). Keep by default; drop only if the user wants just movement details without balances. |
| `o_source_reference` | `sm.reference_no` | `source_reference` | Source reference | Output. Origin document/reference (e.g., GRN/DO), or NULL for stocktake adjustments. Keep by default; drop only if the user asks to hide references. |
| `o_movement_id` | `sm.id` | `movement_id` | Movement ID | Output. System identifier of the movement row. Keep by default as a unique reference; drop only if the user requests a cleaner display without IDs. |

---

## i16 · **统计** Stats

**Stats: Monthly outbound units trend by warehouse**

> Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_movement_date` | `stock_movements.movement_date` | `BETWEEN` | `["2025-08-23", "2026-08-23"]` | date/range | Movement date range | Maps from user phrases about time such as: date ranges (between 2025-01-01 and 2025-12-31), since/until (since 2025-07-01, until 2026-03-31), recent periods (last month, last 3 months, last 12 months, year to date, this year, last year), or specific months (June 2026). Always convert to an absolute start and end date in YYYY-MM-DD. Resolve all relative dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; clamp requested dates to this window. Default: keep the template range 2025-08-23 to 2026-08-23 if the user does not mention time. Disable only if the user explicitly asks for “all time”, “entire dataset”, or equivalent; disabling means include all available dates (2024-09-01 to 2026-08-23). |
| `f_movement_type` | `stock_movements.movement_type` | `=` | `"outbound"` | enum/scalar | Movement type | Maps from user terms describing direction/type: shipments/dispatches/ship-outs/outbound → outbound; receipts/incoming/inbound → inbound; stocktake correction/adjustment → adjustment; “all movement types” → disable this filter. Allowed values (must use exactly one of these or disable): inbound (Stock received into the warehouse), outbound (Stock dispatched from the warehouse), adjustment (Manual stock correction). Default: keep outbound. Change only if the user clearly requests a different type. Disable only if the user explicitly requests all movement types; otherwise do not disable. |
| `f_warehouse` | `stock_movements.warehouse` | `IN` | `["Brisbane", "Melbourne", "Sydney"]` | enum/list | Warehouses | Maps from user mentions of locations: Brisbane, Melbourne, Sydney. Also handle include/exclude phrasing: “Sydney only” → ["Sydney"]; “exclude Melbourne” → include all other allowed values except Melbourne (i.e., ["Brisbane","Sydney"]). This is an enum list; allowed values only: Brisbane, Melbourne, Sydney. Reject any value outside this list (do not guess). Default: keep ["Brisbane","Melbourne","Sydney"] if the user doesn’t specify. Disable only if the user asks for all warehouses; disabling means include every warehouse in the data (i.e., remove the IN filter). |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_year_month` | `DATE_FORMAT(sm.movement_date, '%Y-%m')` | `year_month` | Month | Output shows the calendar year–month (YYYY-MM) bucket of the movement date. Keep this unless the user asks for no timeline (e.g., just totals by warehouse or a single overall total). Drop only when the user explicitly wants a higher-level summary without monthly breakdown. |
| `o_warehouse_name` | `sm.warehouse` | `warehouse_name` | Warehouse | Output shows the warehouse name (city) associated with the movement. Keep this to compare warehouses. Drop only if the user asks for a single combined total across all warehouses or only cares about the time trend without warehouse split. |
| `o_outbound_units` | `SUM(sm.quantity)` | `outbound_units` | Units moved | Output shows the total quantity moved (sum of quantity) within each group. Always keep unless the user asks for a purely dimensional listing without measures (unlikely). This is the primary metric for shipping volume. |

### 分组参数(GROUP BY)

| param_id | 表达式 | 回链输出别名 | business_name | hint |
|---|---|---|---|---|
| `g_year_month` | `DATE_FORMAT(sm.movement_date, '%Y-%m')` | `year_month` | Group by month | Dimension: calendar year–month of movement date. Dropping this aggregates all selected dates together, producing totals per remaining dimensions (e.g., per warehouse) or a single grand total if no other group remains. Drop only if the user asks for a summary without monthly detail (e.g., total by warehouse for the period or overall total). |
| `g_warehouse_name` | `sm.warehouse` | `warehouse_name` | Group by warehouse | Dimension: warehouse (city). Dropping this aggregates across all warehouses, yielding a single time series by month (if month kept) or one overall total for the date range (if month also dropped). Drop only if the user asks to combine all warehouses or not to split by warehouse. |

---

## i18 · **统计** Stats

**Stats: Top products by outbound units (last 90 days)**

> Ranks products by shipment volume over a recent period. Groups by product and sums quantity where movement_type is outbound within the chosen window (e.g., last 90 days), then orders descending to return the top N products; this reflects units shipped to customers. Users vary the lookback window and optionally limit to certain warehouses.

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

### 筛选参数(WHERE)

| param_id | 来源 | 操作符 | 默认值 | 类型/形态 | business_name | hint |
|---|---|---|---|---|---|---|
| `f_movement_date` | `stock_movements.movement_date` | `>=` | `"2026-05-25"` | date/scalar | Earliest movement date | Filter by the earliest movement date to include. Map user phrases like: last 90 days, last month, this month, year to date, since 2026-06-01, from May 1 2026, after 2025-12-31. Set a single start date in format YYYY-MM-DD. Resolve all relative dates to absolute dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23. If the user gives a range (e.g., Jun 1–Jun 30), use the stated start date only; no end date can be applied. DEFAULT: if the user does not mention timing, keep 2026-05-25 (last 90 days). DISABLE: only if the user explicitly asks for all time/no date limit; otherwise keep a start date. |
| `f_movement_type` | `stock_movements.movement_type` | `=` | `"outbound"` | enum/scalar | Movement type | Choose exactly one movement type. Allowed values (must match verbatim): inbound = stock received; outbound = stock dispatched; adjustment = manual correction (can add or remove). DEFAULT: outbound. Change only if the user clearly asks for a different movement type. Reject any value not in the list. DISABLE: only if the user explicitly requests all movement types with no restriction; otherwise keep this filter. |
| `f_warehouse` | `stock_movements.warehouse` | `IN` | `["Brisbane", "Melbourne", "Sydney"]` | enum/list | Warehouses | Limit to one or more warehouses. Allowed values (must match exactly): Brisbane, Melbourne, Sydney. Map user requests like: only Brisbane; Brisbane and Sydney; exclude Melbourne (select Brisbane and Sydney); or Melbourne warehouse. Do not infer from abbreviations (e.g., SYD, Bris) or states; reject values outside the list. DEFAULT: Brisbane, Melbourne, Sydney. Change to the subset the user names. DISABLE: only if the user explicitly asks for all warehouses/no warehouse filter (otherwise keep the default list). |

### 输出参数(SELECT)

| param_id | 表达式 | 别名 | business_name | hint |
|---|---|---|---|---|
| `o_product_id` | `p.id` | `product_id` | Product ID | Shows the internal product identifier. Keep unless the user asks to hide IDs or wants fewer columns (e.g., just SKU/name and units). Drop only when the user requests a narrower output. |
| `o_product_sku` | `p.sku` | `product_sku` | SKU | Shows the product SKU code. Keep by default; drop only if the user asks for fewer columns or does not need SKU. |
| `o_product_name` | `p.name` | `product_name` | Product name | Shows the human-readable product name. Keep by default; drop only if the user asks for fewer columns (e.g., just SKU and units). |
| `o_total_outbound_units` | `SUM(sm.quantity)` | `total_outbound_units` | Total units shipped | Sum of movement quantities for rows that pass the filters (movement_type, date, warehouses). This is the metric used to rank products. Always keep unless the user explicitly requests only identifiers without metrics (rare). |

### 分组参数(GROUP BY)

| param_id | 表达式 | 回链输出别名 | business_name | hint |
|---|---|---|---|---|
| `g_product_id` | `p.id` | `product_id` | Group by product ID | Groups results at the product level. Dropping this makes the aggregation coarser: if you also drop SKU/Name, all products roll up into a single total; if you keep Name or SKU without ID, products sharing that value will be combined. Drop only if the user asks for less detail/roll-up. |
| `g_product_sku` | `p.sku` | `product_sku` | Group by SKU | Groups by product SKU. With product ID kept, dropping SKU does not change totals; it only removes that attribute from the output. If ID is dropped and SKU kept, products with the same SKU (if any) will be combined. Drop only when the user wants less detail. |
| `g_product_name` | `p.name` | `product_name` | Group by product name | Groups by product name. With product ID kept, dropping Name does not change totals; it only removes that attribute from the output. If ID is dropped and Name kept, products sharing the same name will be combined. Drop only when the user asks for less detail. |

---

## 附:机制全披露(由代码常量渲染,与实现一一对应)

### 1. 确定性解析规则(`s3dev/params.py: PARSE_RULES`,零 LLM)

- WHERE:按 AND 展开为叶子条件,每个叶子 = 一个 filter 参数;记录 来源表列/操作符/字面默认值;BETWEEN → value_shape=range(双值),IN → list(多值),其余 → scalar
- SELECT:每个投影(B4 保证全部显式别名)= 一个 output 参数;记录 表达式/别名/单一来源列(纯列或单列函数)
- GROUP BY:每项 = 一个 groupby 参数;表达式与某投影一致时回链其别名(linked_output),便于改写器按别名指称
- param_id 命名:f_/o_/g_ + 列名或别名;同列多条件(如日期区间的 >= 与 <=)追加操作符词缀去重
- value_type 来自语义层列类型:enum_values 存在 → enum;date/time → date;int → integer;decimal/float → number;其余 → string
- 解析后自检:三区条数与 SQL 实际一致(与人工点数核对)、来源列必须存在于语义层、别名唯一

### 2. AI 预填 system prompt(`PREFILL_SYSTEM`,原文)

<details><summary>展开</summary>

```
You are a senior analytics engineer annotating the parameters of a VERIFIED SQL template.

At runtime, an AI rewriter receives a user question plus this template and may ONLY:
change WHERE literal values, disable a WHERE condition, drop output columns, or drop
GROUP BY columns. It can never add or alter anything else. Your annotations are the
rewriter's ONLY instructions for each parameter, so write them for that audience.

For every parameter produce:
- business_name: a short human label in plain business English (2-6 words), as it would
  appear on a form. No SQL jargon, no table prefixes.
- hint: instructions to the rewriter. Content by kind:
  * filter: which user phrasings map to this parameter; how to take the value (exact
    format); and the DEFAULT/DISABLE semantics — when the user does not mention it,
    keep the template default? and when may it be disabled entirely?
    - date parameters: state the value format YYYY-MM-DD, that relative phrases
      ("last month") must be resolved to absolute dates anchored at 2026-08-23, and the
      valid data window 2024-09-01 to 2026-08-23.
    - enum parameters: enumerate EVERY allowed value verbatim with a short meaning;
      values outside the list must be rejected, not guessed.
    - LIKE parameters: partial, case-insensitive contains-match; replace the default
      with the name fragment the user mentions, keeping the surrounding % wildcards.
  * output: what the column shows in business terms, and when the rewriter should keep
    or drop it (dropped only if the user asks for a narrower answer).
  * groupby: what dimension it represents and what dropping it does to the numbers
    (coarser aggregation); it may be dropped only if the user asks for less detail.

Rules:
- English only. Never contradict the SQL or invent capabilities beyond value-change/
  disable/drop. Be specific to THIS template's business meaning (use the intent brief).
- Every param_id from the input must appear exactly once; no extras.
```
</details>

### 3. 实际 user payload 示例(i16,最复杂形态,原文)

<details><summary>展开</summary>

```json
{
 "business_context": "The company is an Australian manufacturer of solar PV mounting systems. This database covers its sales side: products (mounting kits, inverters, energy-management gear, accessories), customers, sales reps, orders with line items, and warehouse inventory with a stock-movement ledger. Amounts are in AUD.",
 "intent": {
  "intent_id": "i16",
  "type": "stats",
  "one_liner": "Stats: Monthly outbound units trend by warehouse",
  "brief": "Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses."
 },
 "sql": "SELECT DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`, sm.warehouse AS `warehouse_name`, SUM(sm.quantity) AS `outbound_units` FROM stock_movements sm WHERE sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23' AND sm.movement_type = 'outbound' AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney') GROUP BY DATE_FORMAT(sm.movement_date, '%Y-%m'), sm.warehouse ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') ASC LIMIT 200",
 "params": {
  "filters": [
   {
    "param_id": "f_movement_date",
    "kind": "filter",
    "source": "stock_movements.movement_date",
    "operator": "BETWEEN",
    "value_type": "date",
    "value_shape": "range",
    "default_value": [
     "2025-08-23",
     "2026-08-23"
    ],
    "predicate_sql": "sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'",
    "column_info": {
     "display_name": "Movement Date",
     "description": "Calendar date of the movement (YYYY‑MM‑DD, day-level granularity).",
     "type": "date",
     "enum_values": null
    }
   },
   {
    "param_id": "f_movement_type",
    "kind": "filter",
    "source": "stock_movements.movement_type",
    "operator": "=",
    "value_type": "enum",
    "value_shape": "scalar",
    "default_value": "outbound",
    "predicate_sql": "sm.movement_type = 'outbound'",
    "column_info": {
     "display_name": "Movement Type",
     "description": "Categorizes the movement as inbound, outbound, or an adjustment. Used together with quantity to determine stock increase or decrease.",
     "type": "varchar(16)",
     "enum_values": [
      {
       "value": "inbound",
       "meaning": "Stock received into the warehouse (e.g., purchase receipt or transfer-in)."
      },
      {
       "value": "outbound",
       "meaning": "Stock dispatched from the warehouse (e.g., customer delivery or transfer-out)."
      },
      {
       "value": "adjustment",
       "meaning": "Manual correction from stocktake or error correction; can increase or decrease stock."
      }
     ]
    }
   },
   {
    "param_id": "f_warehouse",
    "kind": "filter",
    "source": "stock_movements.warehouse",
    "operator": "IN",
    "value_type": "enum",
    "value_shape": "list",
    "default_value": [
     "Brisbane",
     "Melbourne",
     "Sydney"
    ],
    "predicate_sql": "sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')",
    "column_info": {
     "display_name": "Warehouse",
     "description": "Warehouse where the movement occurred. Values indicate the physical warehouse location by city.",
     "type": "varchar(32)",
     "enum_values": [
      {
       "value": "Brisbane",
       "meaning": "Movement occurred at the Brisbane warehouse."
      },
      {
       "value": "Melbourne",
       "meaning": "Movement occurred at the Melbourne warehouse."
      },
      {
       "value": "Sydney",
       "meaning": "Movement occurred at the Sydney warehouse."
      }
     ]
    }
   }
  ],
  "outputs": [
   {
    "param_id": "o_year_month",
    "kind": "output",
    "expr": "DATE_FORMAT(sm.movement_date, '%Y-%m')",
    "alias": "year_month",
    "source": "stock_movements.movement_date",
    "column_info": {
     "display_name": "Movement Date",
     "description": "Calendar date of the movement (YYYY‑MM‑DD, day-level granularity).",
     "type": "date",
     "enum_values": null
    }
   },
   {
    "param_id": "o_warehouse_name",
    "kind": "output",
    "expr": "sm.warehouse",
    "alias": "warehouse_name",
    "source": "stock_movements.warehouse",
    "column_info": {
     "display_name": "Warehouse",
     "description": "Warehouse where the movement occurred. Values indicate the physical warehouse location by city.",
     "type": "varchar(32)",
     "enum_values": [
      {
       "value": "Brisbane",
       "meaning": "Movement occurred at the Brisbane warehouse."
      },
      {
       "value": "Melbourne",
       "meaning": "Movement occurred at the Melbourne warehouse."
      },
      {
       "value": "Sydney",
       "meaning": "Movement occurred at the Sydney warehouse."
      }
     ]
    }
   },
   {
    "param_id": "o_outbound_units",
    "kind": "output",
    "expr": "SUM(sm.quantity)",
    "alias": "outbound_units",
    "source": "stock_movements.quantity",
    "column_info": {
     "display_name": "Quantity Moved",
     "description": "Units moved; positive for inbound/outbound (direction given by movement_type), signed for adjustment",
     "type": "int",
     "enum_values": null
    }
   }
  ],
  "groupbys": [
   {
    "param_id": "g_year_month",
    "kind": "groupby",
    "expr": "DATE_FORMAT(sm.movement_date, '%Y-%m')",
    "source": "stock_movements.movement_date",
    "linked_output": "year_month",
    "column_info": {
     "display_name": "Movement Date",
     "description": "Calendar date of the movement (YYYY‑MM‑DD, day-level granularity).",
     "type": "date",
     "enum_values": null
    }
   },
   {
    "param_id": "g_warehouse_name",
    "kind": "groupby",
    "expr": "sm.warehouse",
    "source": "stock_movements.warehouse",
    "linked_output": "warehouse_name",
    "column_info": {
     "display_name": "Warehouse",
     "description": "Warehouse where the movement occurred. Values indicate the physical warehouse location by city.",
     "type": "varchar(32)",
     "enum_values": [
      {
       "value": "Brisbane",
       "meaning": "Movement occurred at the Brisbane warehouse."
      },
      {
       "value": "Melbourne",
       "meaning": "Movement occurred at the Melbourne warehouse."
      },
      {
       "value": "Sydney",
       "meaning": "Movement occurred at the Sydney warehouse."
      }
     ]
    }
   }
  ]
 },
 "notes": "The demo database contains data from 2024-09-01 to 2026-08-23. Pick default filter values that are guaranteed to match rows; for identity filters pick a concrete value from sample_values."
}
```
</details>

### 4. 预填输出 JSON Schema(`PREFILL_SCHEMA`)

```json
{
 "name": "param_prefill",
 "schema": {
  "type": "object",
  "properties": {
   "params": {
    "type": "array",
    "items": {
     "type": "object",
     "properties": {
      "param_id": {
       "type": "string"
      },
      "business_name": {
       "type": "string"
      },
      "hint": {
       "type": "string"
      }
     },
     "required": [
      "param_id",
      "business_name",
      "hint"
     ],
     "additionalProperties": false
    }
   }
  },
  "required": [
   "params"
  ],
  "additionalProperties": false
 }
}
```

### 5. 预填校验规则(`PREFILL_RULES`,不过即回灌重写)

- param_id 集合必须与骨架完全一致(不缺不多不重复)
- business_name 与 hint 全部非空,英文(CJK 字符零容忍)
- date 型 filter 的 hint 必须含格式说明 `YYYY-MM-DD` 与数据窗口
- enum 型 filter 的 hint 必须逐一含语义层枚举的每个取值字面
- LIKE 型 filter 的 hint 必须说明部分匹配(含 partial/contains/fragment 任一表述)
- 问题回灌重写 ≤ 2 轮,超限报错终止(不静默放行)

### 6. 校验失败回灌模板(`REPAIR_USER_TMPL`)

```
Your annotations failed validation:
{problems}

Return the corrected FULL JSON (all params, same schema). Fix only what is wrong.
```

