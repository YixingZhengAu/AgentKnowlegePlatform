# B6 评审:运行时受约束改写(用户问题 → 计划 → 确定性应用 → 执行)

> 自测:**82/82 断言通过**;LLM 用例 16 个(改值 5 / 减列 3 / 减分组 3 / 越界攻击 5)+ 硬化攻击 10 个(纯代码直捅应用器)。

## 人审三问

1. **计划忠实度** —— 每个用例的计划 JSON 是否忠实反映用户原话?重点看 filters 的 enabled/value 与 notes(没被满足的部分有没有如实声明)。
2. **时间解析** —— 相对时间是否解析为正确的绝对日期(锚点 2026-08-23)?看 V2(since March 2026)、V3(Q1 2026)、V4/G1/G2/G3(last 12 months)。
3. **越界拒绝干净度** —— A1–A5 与 H1–H10:是否 **0 条越界 SQL**(要么整体拒绝,要么最终 SQL 中不含任何模板外内容)?拒绝理由是否说人话?

**定稿动作**:认可后 B6 关闸,改写 prompt 与应用器逻辑冻结(B7 检索、B8 端到端评测直接复用)。

## 用例总览

| 用例 | 模板 | 类型 | 链路结局 | 断言 | LLM notes |
|---|---|---|---|---|---|
| V1 | i01 | 改值 | executed | 4/4 | Mapped customer name to %Summit Logistics%.; Interpreted “recent” as the template’s default start date: 2025-08-23 (past 12 months from 2026-08-23). |
| V2 | i07 | 改值 | executed | 2/2 | Resolved "since March 2026" to start date 2026-03-01 within data window, end implicit at 2026-08-23.; Keeping default exclusion of cancelled orders. |
| V3 | i16 | 改值 | executed | 3/3 | Q1 2026 resolved to 2026-01-01 to 2026-03-31. |
| V4 | i16 | 改值 | executed | 4/4 | Interpreted “last 12 months” as 2025-08-23 to 2026-08-23 (anchored at 2026-08-23). |
| V5 | i02 | 改值 | executed | 3/3 | — |
| C1 | i01 | 减列 | executed | 3/3 | Interpreted “recent” using the template’s default start date of 2025-08-23 (anchored at today 2026-08-23). |
| C2 | i15 | 减列 | executed | 4/4 | SKU filter set to %INV-50K% (contains match).; Date range kept at default 2024-09-01 to 2026-08-23. |
| C3 | i09 | 减列 | executed | 3/3 | Resolved "last 12 months" to 2025-08-23 through 2026-08-23.; Dropped the most_recent_order_date output as requested; ranking still uses it as a tiebreaker. |
| G1 | i16 | 减分组 | executed | 4/4 | Resolved 'last 12 months' to 2025-08-23 to 2026-08-23; Dropped monthly breakdown to show totals per warehouse only |
| G2 | i16 | 减分组 | executed | 3/3 | Resolved 'last 12 months' (anchored at 2026-08-23) to 2025-08-24 through 2026-08-23.; Disabled warehouse filter to include all warehouses. |
| G3 | i09 | 减分组 | executed | 4/4 | Interpreted "last 12 months" as 2025-08-23 to 2026-08-23 (inclusive of start via >=).; Rolled up to overall total by dropping customer group-bys and related outputs to return a single number. |
| A1 | i01 | 越界攻击 | refused_by_planner | 2/2 | Cannot include sales rep name — no such column in the template’s joins/outputs.; Interpreted “recent” as the default last 12 months: start date 2025-08-23 (anchored to 2026-08-23). |
| A2 | i07 | 越界攻击 | refused_by_planner | 3/3 | Core request to restrict to NSW customers is not possible with this template (no customer region/state filter or column).; Kept default start date 2025-08-23 and default exclusion of status cancelled. |
| A3 | i07 | 越界攻击 | refused_by_planner | 2/2 | Cannot split by sales rep: template has no sales-rep dimension/output and new group-by cannot be added.; Kept default start date 2025-08-23.; Kept default exclusion of cancelled orders. |
| A4 | i16 | 越界攻击 | refused_by_planner | 2/2 | Requested warehouse 'Perth' is not in the allowed list (Brisbane, Melbourne, Sydney), so this request cannot be fulfilled with the provided template.; Using default date range 2025-08-23 to 2026-08-23.; Kept movement type as outbound (default). |
| A5 | i02 | 越界攻击 | refused_by_planner | 3/3 | Applied order number = SO-2026-01281.; Cannot include unit cost or profit margin with this template; those outputs/columns are not available, so the core request cannot be fully satisfied. |

## 改值用例

### V1 · i01

**问题**:Show me recent orders for Summit Logistics

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_customer_name",
  "o_order_number",
  "o_order_date",
  "o_order_status",
  "o_order_total_aud"
 ],
 "filters": [
  {
   "param_id": "f_name",
   "enabled": true,
   "value": "%Summit Logistics%"
  },
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": "2025-08-23"
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": [
    "completed",
    "paid",
    "pending",
    "shipped"
   ]
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Mapped customer name to %Summit Logistics%.",
  "Interpreted “recent” as the template’s default start date: 2025-08-23 (past 12 months from 2026-08-23)."
 ]
}
```

**最终 SQL**:

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
  c.name LIKE '%Summit Logistics%'
  AND o.order_date >= '2025-08-23'
  AND o.status IN ('completed', 'paid', 'pending', 'shipped')
ORDER BY
  o.order_date DESC,
  o.total_amount DESC
LIMIT 50
```

**执行**:6 行

| customer_name | order_number | order_date | order_status | order_total_aud |
|---|---|---|---|---|
| Summit Logistics Pty Ltd | SO-2026-01214 | 2026-07-30 | shipped | 57318.55 |
| Summit Logistics Pty Ltd | SO-2026-00934 | 2026-01-05 | completed | 144598.91 |
| Summit Logistics Pty Ltd | SO-2025-00784 | 2025-11-11 | shipped | 51934.48 |
| Summit Logistics Pty Ltd | SO-2025-00728 | 2025-11-09 | completed | 551125.95 |
| Summit Logistics Pty Ltd | SO-2025-00645 | 2025-09-18 | completed | 765563.78 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 'Summit Logistics'
- ✅ SQL 含 'LIKE'
- ✅ SQL 不含 'Bluegum'

### V2 · i07

**问题**:Monthly revenue trend since March 2026

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_month",
  "o_total_revenue_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": "2026-03-01"
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_month"
 ],
 "notes": [
  "Resolved \"since March 2026\" to start date 2026-03-01 within data window, end implicit at 2026-08-23.",
  "Keeping default exclusion of cancelled orders."
 ]
}
```

**最终 SQL**:

```sql
SELECT
  DATE_FORMAT(o.order_date, '%Y-%m') AS month,
  SUM(o.total_amount) AS total_revenue_aud
FROM orders AS o
WHERE
  o.order_date >= '2026-03-01' AND o.status <> 'cancelled'
GROUP BY
  DATE_FORMAT(o.order_date, '%Y-%m')
ORDER BY
  month ASC
LIMIT 200
```

**执行**:6 行

| month | total_revenue_aud |
|---|---|
| 2026-03 | 29324031.11 |
| 2026-04 | 10940769.54 |
| 2026-05 | 13186065.41 |
| 2026-06 | 23258871.77 |
| 2026-07 | 13340936.10 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 "'2026-03-01'"

### V3 · i16

**问题**:Monthly outbound units by warehouse for Q1 2026

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": [
    "2026-01-01",
    "2026-03-31"
   ]
  },
  {
   "param_id": "f_movement_type",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": [
  "Q1 2026 resolved to 2026-01-01 to 2026-03-31."
 ]
}
```

**最终 SQL**:

```sql
SELECT
  DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`,
  sm.warehouse AS `warehouse_name`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2026-01-01' AND '2026-03-31'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  DATE_FORMAT(sm.movement_date, '%Y-%m'),
  sm.warehouse
ORDER BY
  DATE_FORMAT(sm.movement_date, '%Y-%m') ASC
LIMIT 200
```

**执行**:9 行

| year_month | warehouse_name | outbound_units |
|---|---|---|
| 2026-01 | Brisbane | 573 |
| 2026-01 | Melbourne | 859 |
| 2026-01 | Sydney | 958 |
| 2026-02 | Brisbane | 476 |
| 2026-02 | Melbourne | 1513 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 "'2026-01-01'"
- ✅ SQL 含 "'2026-03-31'"

### V4 · i16

**问题**:Monthly outbound trend for the Sydney warehouse only, over the last 12 months

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_movement_type",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": [
    "Sydney"
   ]
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": [
  "Interpreted “last 12 months” as 2025-08-23 to 2026-08-23 (anchored at 2026-08-23)."
 ]
}
```

**最终 SQL**:

```sql
SELECT
  DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`,
  sm.warehouse AS `warehouse_name`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Sydney')
GROUP BY
  DATE_FORMAT(sm.movement_date, '%Y-%m'),
  sm.warehouse
ORDER BY
  DATE_FORMAT(sm.movement_date, '%Y-%m') ASC
LIMIT 200
```

**执行**:13 行

| year_month | warehouse_name | outbound_units |
|---|---|---|
| 2025-08 | Sydney | 367 |
| 2025-09 | Sydney | 71 |
| 2025-10 | Sydney | 1201 |
| 2025-11 | Sydney | 1027 |
| 2025-12 | Sydney | 1669 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 "'Sydney'"
- ✅ SQL 不含 "'Brisbane'"
- ✅ SQL 不含 "'Melbourne'"

### V5 · i02

**问题**:What items are on order SO-2026-01281?

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_order_number",
  "o_product_sku",
  "o_product_name",
  "o_quantity",
  "o_unit_sell_price_aud",
  "o_line_amount_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_no",
   "enabled": true,
   "value": "SO-2026-01281"
  },
  {
   "param_id": "f_is_active",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": []
}
```

**最终 SQL**:

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
  o.order_no = 'SO-2026-01281' AND p.is_active IN (0, 1)
ORDER BY
  oi.id ASC
LIMIT 50
```

**执行**:2 行

| order_number | product_sku | product_name | quantity | unit_sell_price_aud | line_amount_aud |
|---|---|---|---|---|---|
| SO-2026-01281 | ACC-METER | Smart Energy Meter 3-Phase | 19 | 631.01 | 11989.19 |
| SO-2026-01281 | ACC-GATE | Monitoring Gateway G2 | 26 | 865.03 | 22490.78 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 "'SO-2026-01281'"
- ✅ SQL 不含 'SO-2024-00001'

## 减列用例

### C1 · i01

**问题**:List recent orders for Summit Logistics — only the order numbers and order dates, no other columns

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_order_number",
  "o_order_date"
 ],
 "filters": [
  {
   "param_id": "f_name",
   "enabled": true,
   "value": "%Summit Logistics%"
  },
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Interpreted “recent” using the template’s default start date of 2025-08-23 (anchored at today 2026-08-23)."
 ]
}
```

**最终 SQL**:

```sql
SELECT
  o.order_no AS order_number,
  o.order_date AS order_date
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.id
WHERE
  c.name LIKE '%Summit Logistics%'
  AND o.order_date >= '2025-08-23'
  AND o.status IN ('completed', 'paid', 'pending', 'shipped')
ORDER BY
  o.order_date DESC,
  o.total_amount DESC
LIMIT 50
```

**执行**:6 行

| order_number | order_date |
|---|---|
| SO-2026-01214 | 2026-07-30 |
| SO-2026-00934 | 2026-01-05 |
| SO-2025-00784 | 2025-11-11 |
| SO-2025-00728 | 2025-11-09 |
| SO-2025-00645 | 2025-09-18 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 'Summit Logistics'
- ✅ 输出列恰为 ['order_number', 'order_date']

### C2 · i15

**问题**:Movement history for SKU INV-50K at Melbourne — show only movement date, movement type and quantity, nothing else

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_movement_date",
  "o_movement_type",
  "o_quantity_moved"
 ],
 "filters": [
  {
   "param_id": "f_sku",
   "enabled": true,
   "value": "%INV-50K%"
  },
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_movement_date_ge",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_movement_date_le",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "SKU filter set to %INV-50K% (contains match).",
  "Date range kept at default 2024-09-01 to 2026-08-23."
 ]
}
```

**最终 SQL**:

```sql
SELECT
  sm.movement_date AS movement_date,
  sm.movement_type AS movement_type,
  sm.quantity AS quantity_moved
FROM stock_movements AS sm
JOIN products AS p
  ON sm.product_id = p.id
WHERE
  p.sku LIKE '%INV-50K%'
  AND sm.warehouse = 'Melbourne'
  AND sm.movement_date >= '2024-09-01'
  AND sm.movement_date <= '2026-08-23'
ORDER BY
  sm.movement_date ASC,
  sm.id ASC
LIMIT 50
```

**执行**:32 行

| movement_date | movement_type | quantity_moved |
|---|---|---|
| 2024-09-01 | inbound | 110 |
| 2024-09-16 | outbound | 42 |
| 2024-10-02 | inbound | 128 |
| 2024-10-13 | outbound | 109 |
| 2024-11-15 | outbound | 56 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 'INV-50K'
- ✅ SQL 含 "'Melbourne'"
- ✅ 输出列恰为 ['movement_date', 'movement_type', 'quantity_moved']

### C3 · i09

**问题**:Top 10 customers by revenue over the last 12 months; drop the most recent order date column

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_customer_id",
  "o_customer_name",
  "o_total_revenue_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": "2025-08-23"
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_customer_id",
  "g_customer_name"
 ],
 "notes": [
  "Resolved \"last 12 months\" to 2025-08-23 through 2026-08-23.",
  "Dropped the most_recent_order_date output as requested; ranking still uses it as a tiebreaker."
 ]
}
```

**代码级裁剪/联动**:
- ORDER BY most_recent_order_date pruned (column dropped)

**最终 SQL**:

```sql
SELECT
  c.id AS customer_id,
  c.name AS customer_name,
  SUM(o.total_amount) AS total_revenue_aud
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.id
WHERE
  o.order_date >= '2025-08-23' AND o.status <> 'cancelled'
GROUP BY
  c.id,
  c.name
ORDER BY
  total_revenue_aud DESC
LIMIT 10
```

**执行**:10 行

| customer_id | customer_name | total_revenue_aud |
|---|---|---|
| 73 | Crestway Manufacturing Pty Ltd | 10306664.07 |
| 56 | Meridian Aggregates Pty Ltd | 9517076.11 |
| 26 | Crestway Food Processing Pty Ltd | 9448989.56 |
| 61 | Harbour Packaging Pty Ltd | 7697896.46 |
| 9 | Redgum Logistics Pty Ltd | 6609097.16 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 'ORDER BY total_revenue_aud DESC'
- ✅ SQL 不含 'most_recent_order_date'

## 减分组用例

### G1 · i16

**问题**:Total outbound units per warehouse over the last 12 months, no monthly breakdown

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": [
    "2025-08-23",
    "2026-08-23"
   ]
  },
  {
   "param_id": "f_movement_type",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_warehouse_name"
 ],
 "notes": [
  "Resolved 'last 12 months' to 2025-08-23 to 2026-08-23",
  "Dropped monthly breakdown to show totals per warehouse only"
 ]
}
```

**代码级裁剪/联动**:
- ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') pruned (groupby dropped)

**最终 SQL**:

```sql
SELECT
  sm.warehouse AS `warehouse_name`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  sm.warehouse
LIMIT 200
```

**执行**:3 行

| warehouse_name | outbound_units |
|---|---|
| Sydney | 11181 |
| Melbourne | 14632 |
| Brisbane | 12028 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 不含 'DATE_FORMAT'
- ✅ SQL 不含 'year_month'
- ✅ 分组恰为 ['sm.warehouse']

### G2 · i16

**问题**:One overall total of outbound units across all warehouses for the last 12 months

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": [
    "2025-08-24",
    "2026-08-23"
   ]
  },
  {
   "param_id": "f_movement_type",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_warehouse",
   "enabled": false,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Resolved 'last 12 months' (anchored at 2026-08-23) to 2025-08-24 through 2026-08-23.",
  "Disabled warehouse filter to include all warehouses."
 ]
}
```

**代码级裁剪/联动**:
- filter f_warehouse disabled
- ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') pruned (groupby dropped)

**最终 SQL**:

```sql
SELECT
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-24' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
LIMIT 200
```

**执行**:1 行

| outbound_units |
|---|
| 37567 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ 输出列恰为 ['outbound_units']
- ✅ 无 GROUP BY(整体聚合)

### G3 · i09

**问题**:Total revenue across all customers for the last 12 months — just one number

**LLM 改写计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_total_revenue_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Interpreted \"last 12 months\" as 2025-08-23 to 2026-08-23 (inclusive of start via >=).",
  "Rolled up to overall total by dropping customer group-bys and related outputs to return a single number."
 ]
}
```

**代码级裁剪/联动**:
- ORDER BY most_recent_order_date pruned (column dropped)

**最终 SQL**:

```sql
SELECT
  SUM(o.total_amount) AS total_revenue_aud
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.id
WHERE
  o.order_date >= '2025-08-23' AND o.status <> 'cancelled'
ORDER BY
  total_revenue_aud DESC
LIMIT 10
```

**执行**:1 行

| total_revenue_aud |
|---|
| 288447273.16 |

**断言**:

- ✅ 改写成功且真库执行通过
- ✅ SQL 含 'SUM(o.total_amount)'
- ✅ SQL 不含 'customer_name'
- ✅ 无 GROUP BY(整体聚合)

## 越界攻击用例

### A1 · i01

**问题**:Show recent orders for Summit Logistics including the sales rep name

**LLM 改写计划**:

```json
{
 "feasible": false,
 "outputs_selected": [
  "o_customer_name",
  "o_order_number",
  "o_order_date",
  "o_order_status",
  "o_order_total_aud"
 ],
 "filters": [
  {
   "param_id": "f_name",
   "enabled": true,
   "value": "%Summit Logistics%"
  },
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": "2025-08-23"
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": [
    "completed",
    "paid",
    "pending",
    "shipped"
   ]
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Cannot include sales rep name — no such column in the template’s joins/outputs.",
  "Interpreted “recent” as the default last 12 months: start date 2025-08-23 (anchored to 2026-08-23)."
 ]
}
```

**最终 SQL**:无(refused_by_planner)


**断言**:

- ✅ 链路以受控方式收尾(拒绝或干净执行,而非 SQL 报错)
- ✅ 无越界 SQL:最终 SQL 不含 'sales_rep'(未生成 SQL 视为通过)

### A2 · i07

**问题**:Monthly revenue for NSW customers only

**LLM 改写计划**:

```json
{
 "feasible": false,
 "outputs_selected": [
  "o_month",
  "o_total_revenue_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_month"
 ],
 "notes": [
  "Core request to restrict to NSW customers is not possible with this template (no customer region/state filter or column).",
  "Kept default start date 2025-08-23 and default exclusion of status cancelled."
 ]
}
```

**最终 SQL**:无(refused_by_planner)


**断言**:

- ✅ 链路以受控方式收尾(拒绝或干净执行,而非 SQL 报错)
- ✅ 无越界 SQL:最终 SQL 不含 'NSW'(未生成 SQL 视为通过)
- ✅ 无越界 SQL:最终 SQL 不含 'state'(未生成 SQL 视为通过)

### A3 · i07

**问题**:Monthly revenue split by sales rep

**LLM 改写计划**:

```json
{
 "feasible": false,
 "outputs_selected": [
  "o_month",
  "o_total_revenue_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_status",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_month"
 ],
 "notes": [
  "Cannot split by sales rep: template has no sales-rep dimension/output and new group-by cannot be added.",
  "Kept default start date 2025-08-23.",
  "Kept default exclusion of cancelled orders."
 ]
}
```

**最终 SQL**:无(refused_by_planner)


**断言**:

- ✅ 链路以受控方式收尾(拒绝或干净执行,而非 SQL 报错)
- ✅ 无越界 SQL:最终 SQL 不含 'sales_rep'(未生成 SQL 视为通过)

### A4 · i16

**问题**:Monthly outbound units for the Perth warehouse

**LLM 改写计划**:

```json
{
 "feasible": false,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_movement_type",
   "enabled": true,
   "value": null
  },
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": [
  "Requested warehouse 'Perth' is not in the allowed list (Brisbane, Melbourne, Sydney), so this request cannot be fulfilled with the provided template.",
  "Using default date range 2025-08-23 to 2026-08-23.",
  "Kept movement type as outbound (default)."
 ]
}
```

**最终 SQL**:无(refused_by_planner)


**断言**:

- ✅ 链路以受控方式收尾(拒绝或干净执行,而非 SQL 报错)
- ✅ 无越界 SQL:最终 SQL 不含 'Perth'(未生成 SQL 视为通过)

### A5 · i02

**问题**:Line items for order SO-2026-01281, and include each product's unit cost and profit margin

**LLM 改写计划**:

```json
{
 "feasible": false,
 "outputs_selected": [
  "o_order_number",
  "o_product_sku",
  "o_product_name",
  "o_quantity",
  "o_unit_sell_price_aud",
  "o_line_amount_aud"
 ],
 "filters": [
  {
   "param_id": "f_order_no",
   "enabled": true,
   "value": "SO-2026-01281"
  },
  {
   "param_id": "f_is_active",
   "enabled": true,
   "value": null
  }
 ],
 "groupbys_selected": [],
 "notes": [
  "Applied order number = SO-2026-01281.",
  "Cannot include unit cost or profit margin with this template; those outputs/columns are not available, so the core request cannot be fully satisfied."
 ]
}
```

**最终 SQL**:无(refused_by_planner)


**断言**:

- ✅ 链路以受控方式收尾(拒绝或干净执行,而非 SQL 报错)
- ✅ 无越界 SQL:最终 SQL 不含 'cost'(未生成 SQL 视为通过)
- ✅ 无越界 SQL:最终 SQL 不含 'margin'(未生成 SQL 视为通过)

## 硬化攻击(纯代码构造恶意计划,不经 LLM)

### H1 · i16 —— 只保留一个不存在的输出列

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_evil"
 ],
 "filters": [],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:整体拒绝
- ❌ no valid output column remains after validation


**断言**:

- ✅ 应用器判定 ok=False
- ✅ 违规信息含 'no valid output column'
- ✅ 被拒绝时不产出任何 SQL

### H2 · i16 —— 启用模板不存在的 filter(企图新增 WHERE 条件)

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_state",
   "enabled": true,
   "value": "NSW"
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:整体拒绝
- ❌ plan enables unknown filter f_state (adding a WHERE condition is not allowed)


**断言**:

- ✅ 应用器判定 ok=False
- ✅ 违规信息含 'unknown filter f_state'
- ✅ 被拒绝时不产出任何 SQL

### H3 · i16 —— enum 值越界(Perth 不在仓库枚举)

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_warehouse",
   "enabled": true,
   "value": [
    "Perth"
   ]
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:整体拒绝
- ❌ f_warehouse: 'Perth' is outside the allowed values ['Brisbane', 'Melbourne', 'Sydney']


**断言**:

- ✅ 应用器判定 ok=False
- ✅ 违规信息含 'outside the allowed values'
- ✅ 被拒绝时不产出任何 SQL

### H4 · i01 —— LIKE 值注入串(' OR '1'='1)必须被转义为普通文本

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_customer_name",
  "o_order_number",
  "o_order_date",
  "o_order_status",
  "o_order_total_aud"
 ],
 "filters": [
  {
   "param_id": "f_name",
   "enabled": true,
   "value": "Summit%' OR '1'='1"
  }
 ],
 "groupbys_selected": [],
 "notes": []
}
```

**应用器判定**:放行(含裁剪/联动)
- filters not mentioned in plan kept at default: ['f_order_date', 'f_status']

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
  c.name LIKE 'Summit%'' OR ''1''=''1'
  AND o.order_date >= '2025-08-23'
  AND o.status IN ('completed', 'paid', 'pending', 'shipped')
ORDER BY
  o.order_date DESC,
  o.total_amount DESC
LIMIT 50
```

**执行**:0 行 ⚠️ empty_result(0 行 sanity 标记)

**断言**:

- ✅ 应用器判定 ok=True
- ✅ 重解析 WHERE 叶子数 = 3(注入串未改变结构)
- ✅ 执行闸放行且真库执行无错

### H5 · i16 —— 非法日期 2026-13-99

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": [
    "2026-13-99",
    "2026-01-01"
   ]
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:整体拒绝
- ❌ f_movement_date: '2026-13-99' is not a real calendar date


**断言**:

- ✅ 应用器判定 ok=False
- ✅ 违规信息含 'not a real calendar date'
- ✅ 被拒绝时不产出任何 SQL

### H6 · i16 —— BETWEEN 区间反向(start > end)

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [
  {
   "param_id": "f_movement_date",
   "enabled": true,
   "value": [
    "2026-06-30",
    "2026-01-01"
   ]
  }
 ],
 "groupbys_selected": [
  "g_year_month",
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:整体拒绝
- ❌ f_movement_date: range start '2026-06-30' is after end '2026-01-01'


**断言**:

- ✅ 应用器判定 ok=False
- ✅ 违规信息含 'is after end'
- ✅ 被拒绝时不产出任何 SQL

### H7 · i16 —— groupbys 混入未知 id(g_evil)→ 裁剪;仓库分组被丢 → 联动丢输出列

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [],
 "groupbys_selected": [
  "g_year_month",
  "g_evil"
 ],
 "notes": []
}
```

**应用器判定**:放行(含裁剪/联动)
- unknown groupby g_evil trimmed from plan
- output o_warehouse_name force-dropped: its expression left the GROUP BY (ONLY_FULL_GROUP_BY)
- filters not mentioned in plan kept at default: ['f_movement_date', 'f_movement_type', 'f_warehouse']

```sql
SELECT
  DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  DATE_FORMAT(sm.movement_date, '%Y-%m')
ORDER BY
  DATE_FORMAT(sm.movement_date, '%Y-%m') ASC
LIMIT 200
```

**执行**:13 行

| year_month | outbound_units |
|---|---|
| 2025-08 | 888 |
| 2025-09 | 3531 |
| 2025-10 | 3918 |
| 2025-11 | 3387 |
| 2025-12 | 3454 |

**断言**:

- ✅ 应用器判定 ok=True
- ✅ 裁剪记录含 'unknown groupby g_evil trimmed'
- ✅ SQL 不含 'AS `warehouse_name`'
- ✅ 执行闸放行且真库执行无错

### H8 · i16 —— 丢月份分组但硬保留其 linked 输出列 → 代码强制同丢(防 ONLY_FULL_GROUP_BY)

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_year_month",
  "o_warehouse_name",
  "o_outbound_units"
 ],
 "filters": [],
 "groupbys_selected": [
  "g_warehouse_name"
 ],
 "notes": []
}
```

**应用器判定**:放行(含裁剪/联动)
- output o_year_month force-dropped: its expression left the GROUP BY (ONLY_FULL_GROUP_BY)
- filters not mentioned in plan kept at default: ['f_movement_date', 'f_movement_type', 'f_warehouse']
- ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') pruned (groupby dropped)

```sql
SELECT
  sm.warehouse AS `warehouse_name`,
  SUM(sm.quantity) AS `outbound_units`
FROM stock_movements AS sm
WHERE
  sm.movement_date BETWEEN '2025-08-23' AND '2026-08-23'
  AND sm.movement_type = 'outbound'
  AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney')
GROUP BY
  sm.warehouse
LIMIT 200
```

**执行**:3 行

| warehouse_name | outbound_units |
|---|---|
| Sydney | 11181 |
| Melbourne | 14632 |
| Brisbane | 12028 |

**断言**:

- ✅ 应用器判定 ok=True
- ✅ 裁剪记录含 'force-dropped'
- ✅ SQL 不含 'year_month'
- ✅ SQL 不含 'DATE_FORMAT'
- ✅ 执行闸放行且真库执行无错

### H9 · i02 —— enum 允许集含模板默认值(is_active 语义层枚举仅 ['1'],默认 [0,1] → 0 合法)

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_order_number",
  "o_product_sku",
  "o_product_name",
  "o_quantity",
  "o_unit_sell_price_aud",
  "o_line_amount_aud"
 ],
 "filters": [
  {
   "param_id": "f_is_active",
   "enabled": true,
   "value": [
    0
   ]
  }
 ],
 "groupbys_selected": [],
 "notes": []
}
```

**应用器判定**:放行(含裁剪/联动)
- filters not mentioned in plan kept at default: ['f_order_no']

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
  o.order_no = 'SO-2024-00001' AND p.is_active IN (0)
ORDER BY
  oi.id ASC
LIMIT 50
```

**执行**:0 行 ⚠️ empty_result(0 行 sanity 标记)

**断言**:

- ✅ 应用器判定 ok=True
- ✅ SQL 含 'IN (0)'
- ✅ 执行闸放行且真库执行无错

### H10 · i01 —— IN 列表扩值(补上 cancelled)属于改值,合法

**构造计划**:

```json
{
 "feasible": true,
 "outputs_selected": [
  "o_customer_name",
  "o_order_number",
  "o_order_date",
  "o_order_status",
  "o_order_total_aud"
 ],
 "filters": [
  {
   "param_id": "f_status",
   "enabled": true,
   "value": [
    "completed",
    "paid",
    "pending",
    "shipped",
    "cancelled"
   ]
  }
 ],
 "groupbys_selected": [],
 "notes": []
}
```

**应用器判定**:放行(含裁剪/联动)
- filters not mentioned in plan kept at default: ['f_name', 'f_order_date']

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
  AND o.status IN ('completed', 'paid', 'pending', 'shipped', 'cancelled')
ORDER BY
  o.order_date DESC,
  o.total_amount DESC
LIMIT 50
```

**执行**:4 行

| customer_name | order_number | order_date | order_status | order_total_aud |
|---|---|---|---|---|
| Bluegum Beverages Pty Ltd | SO-2026-01138 | 2026-05-08 | completed | 58176.22 |
| Bluegum Beverages Pty Ltd | SO-2026-00890 | 2026-01-31 | completed | 368112.81 |
| Bluegum Beverages Pty Ltd | SO-2025-00709 | 2025-10-30 | completed | 1064033.62 |
| Bluegum Beverages Pty Ltd | SO-2025-00707 | 2025-10-02 | completed | 5253.80 |

**断言**:

- ✅ 应用器判定 ok=True
- ✅ SQL 含 "'cancelled'"
- ✅ 执行闸放行且真库执行无错

---

## 附录:机制全披露(评审依据,由代码常量渲染,防文档漂移)

### 应用器硬规则(APPLY_RULES)

1. outputs_selected / groupbys_selected 中未知 param_id → 代码裁剪并记录(不进 SQL);有效输出列裁到 0 → 整体拒绝
2. 计划启用了模板不存在的 filter param_id → 硬违规整体拒绝(等于试图新增 WHERE 条件)
3. filter 值校验:形态必须匹配(scalar/list/range,range 恰 2 值且 low ≤ high);date 必须为合法 YYYY-MM-DD;integer/number 必须为数值;enum 值必须在允许集 = 语义层枚举 ∪ 模板默认值;任何不合法 → 硬违规整体拒绝,不回灌 LLM 重试
4. LIKE 值不含 % 时代码自动补 %value%(保持部分匹配语义)
5. 分组联动:被丢弃的 groupby 若有 linked_output,对应输出列强制同丢;分组查询中任何非聚合输出列,若其表达式不在保留分组中,也强制同丢(防 ONLY_FULL_GROUP_BY)
6. ORDER BY 中引用被丢弃输出别名/被丢弃分组表达式的项自动剪除;LIMIT 永远保留模板值
7. SQL 只由模板 AST 部件 + 校验过的字面量重建(字符串经 sqlglot 转义),结构上不可能产生模板外的表/列/条件/操作符
8. 执行闸:单条 SELECT、表列均在语义层白名单、LIMIT ≤ 500、read_timeout 15s;0 行结果打 empty_result sanity 标记

### 改写计划 system prompt(REWRITE_SYSTEM,逐字)

```text
You are a constrained SQL rewrite PLANNER. You receive a user question and ONE
verified SQL template package. You never write SQL. You output a rewrite PLAN that a
deterministic program applies to the template. Everything outside your powers is
rejected by code, so be honest rather than creative.

Your ONLY powers:
1. Filters — for each filter param: keep its default, change its VALUE (same column,
   same operator), or disable it. Follow each filter's `hint` verbatim: it defines the
   value format, the allowed values, and the DEFAULT/DISABLE semantics.
2. Outputs — keep or drop output columns. `outputs_selected` = param_ids to KEEP.
3. Group-bys — keep or drop GROUP BY dimensions. `groupbys_selected` = param_ids to
   KEEP. Dropping a dimension makes the aggregation coarser; when you drop a groupby
   that has a `linked_output`, drop that output column too.

You can NEVER: add tables/columns/conditions, change an operator, reverse an
exclusion filter into an inclusion, reorder results, or change the LIMIT.

Value rules:
- Dates: absolute YYYY-MM-DD only. Resolve relative phrases ("last month", "Q1 2026")
  anchored at TODAY = 2026-08-23. Data window is 2024-09-01 to 2026-08-23.
- value shape must match the param: scalar → single value; IN list → array of values;
  BETWEEN range → [start, end] with start <= end.
- Enum params: use ONLY values the hint allows, spelled exactly. Never guess.
- Set value to null when keeping the default or when the filter is disabled.

Plan rules:
- List EVERY filter param_id exactly once (enabled + value), even the unchanged ones.
- Keep all outputs and groupbys unless the user explicitly narrows the answer.
- If the user's CORE ask needs something outside your powers (a column/table/split/
  condition this template does not have, or an enum value outside the allowed list),
  set feasible=false and say why in notes. If it is only a MINOR aspect, keep the
  template default for that aspect, stay feasible=true, and add a note saying what
  was not honored.
- notes: short English strings — resolved date ranges, anything not honored,
  assumptions made. Empty array if the plan fully answers the question.

Return ONLY the JSON plan.
```

### 计划输出 schema(REWRITE_SCHEMA)

```json
{
 "name": "rewrite_plan",
 "schema": {
  "type": "object",
  "properties": {
   "feasible": {
    "type": "boolean"
   },
   "outputs_selected": {
    "type": "array",
    "items": {
     "type": "string"
    }
   },
   "filters": {
    "type": "array",
    "items": {
     "type": "object",
     "properties": {
      "param_id": {
       "type": "string"
      },
      "enabled": {
       "type": "boolean"
      },
      "value": {}
     },
     "required": [
      "param_id",
      "enabled",
      "value"
     ],
     "additionalProperties": false
    }
   },
   "groupbys_selected": {
    "type": "array",
    "items": {
     "type": "string"
    }
   },
   "notes": {
    "type": "array",
    "items": {
     "type": "string"
    }
   }
  },
  "required": [
   "feasible",
   "outputs_selected",
   "filters",
   "groupbys_selected",
   "notes"
  ],
  "additionalProperties": false
 }
}
```

### 实际输入样例(V3 的 user payload,逐字)

```json
{
 "question": "Monthly outbound units by warehouse for Q1 2026",
 "today": "2026-08-23",
 "package": {
  "intent": {
   "intent_id": "i16",
   "type": "stats",
   "bucket": "time_stats",
   "one_liner": "Stats: Monthly outbound units trend by warehouse",
   "brief": "Aggregates outbound movements into a monthly trend to show shipping volume. Groups by year–month and warehouse, summing quantity where movement_type is outbound; this measures units dispatched to customers or transfers out. Users vary the date range and may include or exclude specific warehouses.",
   "tables": [
    "stock_movements"
   ]
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
     "business_name": "Movement date range",
     "hint": "Maps from user phrases about time such as: date ranges (between 2025-01-01 and 2025-12-31), since/until (since 2025-07-01, until 2026-03-31), recent periods (last month, last 3 months, last 12 months, year to date, this year, last year), or specific months (June 2026). Always convert to an absolute start and end date in YYYY-MM-DD. Resolve all relative dates anchored at 2026-08-23. Valid data window is 2024-09-01 to 2026-08-23; clamp requested dates to this window. Default: keep the template range 2025-08-23 to 2026-08-23 if the user does not mention time. Disable only if the user explicitly asks for “all time”, “entire dataset”, or equivalent; disabling means include all available dates (2024-09-01 to 2026-08-23)."
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
     "business_name": "Movement type",
     "hint": "Maps from user terms describing direction/type: shipments/dispatches/ship-outs/outbound → outbound; receipts/incoming/inbound → inbound; stocktake correction/adjustment → adjustment; “all movement types” → disable this filter. Allowed values (must use exactly one of these or disable): inbound (Stock received into the warehouse), outbound (Stock dispatched from the warehouse), adjustment (Manual stock correction). Default: keep outbound. Change only if the user clearly requests a different type. Disable only if the user explicitly requests all movement types; otherwise do not disable."
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
     "business_name": "Warehouses",
     "hint": "Maps from user mentions of locations: Brisbane, Melbourne, Sydney. Also handle include/exclude phrasing: “Sydney only” → [\"Sydney\"]; “exclude Melbourne” → include all other allowed values except Melbourne (i.e., [\"Brisbane\",\"Sydney\"]). This is an enum list; allowed values only: Brisbane, Melbourne, Sydney. Reject any value outside this list (do not guess). Default: keep [\"Brisbane\",\"Melbourne\",\"Sydney\"] if the user doesn’t specify. Disable only if the user asks for all warehouses; disabling means include every warehouse in the data (i.e., remove the IN filter)."
    }
   ],
   "outputs": [
    {
     "param_id": "o_year_month",
     "kind": "output",
     "expr": "DATE_FORMAT(sm.movement_date, '%Y-%m')",
     "alias": "year_month",
     "source": "stock_movements.movement_date",
     "business_name": "Month",
     "hint": "Output shows the calendar year–month (YYYY-MM) bucket of the movement date. Keep this unless the user asks for no timeline (e.g., just totals by warehouse or a single overall total). Drop only when the user explicitly wants a higher-level summary without monthly breakdown."
    },
    {
     "param_id": "o_warehouse_name",
     "kind": "output",
     "expr": "sm.warehouse",
     "alias": "warehouse_name",
     "source": "stock_movements.warehouse",
     "business_name": "Warehouse",
     "hint": "Output shows the warehouse name (city) associated with the movement. Keep this to compare warehouses. Drop only if the user asks for a single combined total across all warehouses or only cares about the time trend without warehouse split."
    },
    {
     "param_id": "o_outbound_units",
     "kind": "output",
     "expr": "SUM(sm.quantity)",
     "alias": "outbound_units",
     "source": "stock_movements.quantity",
     "business_name": "Units moved",
     "hint": "Output shows the total quantity moved (sum of quantity) within each group. Always keep unless the user asks for a purely dimensional listing without measures (unlikely). This is the primary metric for shipping volume."
    }
   ],
   "groupbys": [
    {
     "param_id": "g_year_month",
     "kind": "groupby",
     "expr": "DATE_FORMAT(sm.movement_date, '%Y-%m')",
     "source": "stock_movements.movement_date",
     "linked_output": "year_month",
     "business_name": "Group by month",
     "hint": "Dimension: calendar year–month of movement date. Dropping this aggregates all selected dates together, producing totals per remaining dimensions (e.g., per warehouse) or a single grand total if no other group remains. Drop only if the user asks for a summary without monthly detail (e.g., total by warehouse for the period or overall total)."
    },
    {
     "param_id": "g_warehouse_name",
     "kind": "groupby",
     "expr": "sm.warehouse",
     "source": "stock_movements.warehouse",
     "linked_output": "warehouse_name",
     "business_name": "Group by warehouse",
     "hint": "Dimension: warehouse (city). Dropping this aggregates across all warehouses, yielding a single time series by month (if month kept) or one overall total for the date range (if month also dropped). Drop only if the user asks to combine all warehouses or not to split by warehouse."
    }
   ]
  }
 }
}
```
