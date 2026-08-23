# B8 端到端离线评测评审(Phase B 总闸门)

> 生成于 2026-08-23 19:41 · 模式 `check(重放已存计划,零 LLM)` · 评测集 20 题 · embedding `text-embedding-3-small`/1536 · 链路 = 检索(B7) → 改写计划(B6) → 应用器 → 执行闸

## 人审三问(这一关过了,AI 部分定型,Phase C 只做工程化迁移)

1. **链路的内在逻辑对不对**:看 §2 每一题的五步中间产物(检索候选 → 命中模板 → 改写计划 → 最终 SQL → 结果),每一步的推断是不是你要的那个推断?尤其看计划里的`notes`(模型的推理理由)与应用器的裁剪记录。
2. **拒答的两种口径分得对不对**:非问数(§2 E18–E20,检索层拦,零 LLM 成本)与模板外(§2 E14–E17,命中最近模板后由 planner 拒)—— 这两类回给用户的话术是不是你要的。
3. **评测集够不够格当回归资产**:题目覆盖(§1 分类表)与断言强度(每题末尾的断言表)是否足以在 Phase C 迁移后守住「迁移无损」?缺的题直接加进 `out/eval_cases.json`。

## 结论速览

| 指标 | 结果 | 通过线 |
| --- | --- | --- |
| 总体通过率 | **20/20 = 100.0%** | ≥ 90% |
| 越界/拒答类(硬闸门) | **7/7** | 100% |
| 以 SQL 执行错误收尾 | 0 题 | 0 |
| 单题端到端耗时 | 均 7861 ms(min 5 / max 19113) —— 沿用上一次 --all 的记录,重放模式不计时 | — |

### 分类明细

| 类别 | 通过 | 说明 |
| --- | --- | --- |
| 值改写(query) | 3/3 |  |
| 值改写(stats) | 4/4 |  |
| 减列 | 3/3 |  |
| 减分组 | 3/3 |  |
| 模板外拒答 | 4/4 | 硬闸门,必须 100% |
| 非问数拒答 | 3/3 | 硬闸门,必须 100% |

### 终态分布

| 终态 | 题数 | 含义 |
| --- | --- | --- |
| `executed` | 13 | 跑通取到数 |
| `refused_non_data` | 3 | 检索层判非问数,交回 S4,零 LLM 成本 |
| `refused_out_of_template` | 4 | 是问数、命中最近模板、模板答不了 |

全部通过。

### ⚠ 踩线过的题(检索 confident=False,top1−top2 < 0.03)

E05 —— 这些题命中的模板是对的,但两个候选咬得近。B7 的设计是把这个信号交给 S4 决定加不加一步 LLM 复核;B8 离线链路不替 S4 做决定,照跑 top1 并在此单列。

---

## §1 评测集构成(手写,`out/eval_cases.json`,人可增删改)

| 编号 | 类别 | 问题 | 核心断言 |
| --- | --- | --- | --- |
| E01 | 值改写(query) | Show me the latest orders for Boomerang Textiles Pty Ltd | 终态 executed;意图 i01;SQL 含 `Boomerang Textiles` |
| E02 | 值改写(query) | What's on order SO-2026-01270? | 终态 executed;意图 i02;SQL 含 `SO-2026-01270` |
| E03 | 值改写(query) | Stock movement history for HC-300 at the Brisbane warehouse | 终态 executed;意图 i15;SQL 含 `HC-300`/`Brisbane` |
| E04 | 值改写(stats) | Monthly revenue trend since January 2026 | 终态 executed;意图 i07;SQL 含 `2026-01-01` |
| E05 | 值改写(stats) | Monthly outbound units for Melbourne and Brisbane over the last 6 months | 终态 executed;意图 i16;SQL 含 `Melbourne`/`Brisbane`;SQL 不含 `Sydney` |
| E06 | 值改写(stats) | Which products shipped the most units out of Sydney in the last 30 days? | 终态 executed;意图 i18;SQL 含 `Sydney`;SQL 不含 `Brisbane`/`Melbourne` |
| E07 | 值改写(stats) | Who were our biggest customers by revenue in the past 6 months? | 终态 executed;意图 i09 |
| E08 | 减列 | For order SO-2026-01281 just show the product name and the quantity | 终态 executed;意图 i02;列不含 `unit_sell_price_aud`/`line_amount_aud` |
| E09 | 减列 | Movement history for INV-110K at Sydney — only the movement date and the quantity, nothing else | 终态 executed;意图 i15;SQL 含 `INV-110K`/`Sydney`;列不含 `balance_after`/`source_reference`/`movement_id` |
| E10 | 减列 | Recent orders for Pacific Dairy Co-op Pty Ltd — just the order number and the order total | 终态 executed;意图 i01;列不含 `order_status` |
| E11 | 减分组 | Total outbound units per warehouse over the last 6 months, without the monthly breakdown | 终态 executed;意图 i16;列不含 `year_month` |
| E12 | 减分组 | Units shipped in the last 90 days per SKU only — no product id, no product name | 终态 executed;意图 i18;列不含 `product_id`/`product_name` |
| E13 | 减分组 | What's our total revenue since January 2026 — one number, no monthly split | 终态 executed;意图 i07;列不含 `month` |
| E14 | 模板外拒答 | Monthly revenue broken down by product category | 终态 refused_out_of_template;不生成 SQL |
| E15 | 模板外拒答 | Top 10 customers by profit margin over the last 12 months | 终态 refused_out_of_template;不生成 SQL |
| E16 | 模板外拒答 | Recent orders for Summit Manufacturing Pty Ltd plus the customer's phone number and credit limit | 终态 refused_out_of_template;不生成 SQL |
| E17 | 模板外拒答 | Monthly outbound units by warehouse, but only for battery cabinet products | 终态 refused_out_of_template;不生成 SQL |
| E18 | 非问数拒答 | What's the warranty period on the HC-300 battery cabinet? | 终态 refused_non_data;不生成 SQL;零 LLM |
| E19 | 非问数拒答 | How do I commission the INV-50K inverter on site? | 终态 refused_non_data;不生成 SQL;零 LLM |
| E20 | 非问数拒答 | Thanks, that's all for today. | 终态 refused_non_data;不生成 SQL;零 LLM |

---

## §2 逐题链路详解(人审主战场)


#### E01 · 值改写(query) — ✅ 通过

**问题**:Show me the latest orders for Boomerang Textiles Pty Ltd

**① 检索**:i01 0.871 / i07 0.505 / i18 0.495 → 判定 `confident_hit`(top1 0.871,边距 0.366)  
命中的面:`List all orders for Boomerang Textiles Pty Ltd placed since 2026-01-01, with status and order total, newest first.`(question)

**② 命中模板**:`i01` Query: Recent orders for a specific customer

**③ 计划**:feasible=`True`;输出 5 列 `o_customer_name, o_order_number, o_order_date, o_order_status, o_order_total_aud`;分组 `—`  
筛选:f_name="%Boomerang Textiles Pty Ltd%", f_order_date=null, f_status=null  
> Using default start date 2025-08-23 since no specific date was requested.  
> “Latest” is satisfied by existing ORDER BY (most recent first) and LIMIT 50.  

**④ 最终 SQL**

```sql
SELECT c.name AS customer_name, o.order_no AS order_number, o.order_date AS order_date, o.status AS order_status, o.total_amount AS order_total_aud FROM orders AS o JOIN customers AS c ON o.customer_id = c.id WHERE c.name LIKE '%Boomerang Textiles Pty Ltd%' AND o.order_date >= '2025-08-23' AND o.status IN ('completed', 'paid', 'pending', 'shipped') ORDER BY o.order_date DESC, o.total_amount DESC LIMIT 50
```

**⑤ 执行**:5 行,列 `customer_name, order_number, order_date, order_status, order_total_aud`

| customer_name | order_number | order_date | order_status | order_total_aud |
| --- | --- | --- | --- | --- |
| Boomerang Textiles Pty Ltd | SO-2026-01137 | 2026-05-05 | completed | 20335.38 |
| Boomerang Textiles Pty Ltd | SO-2026-00880 | 2026-01-24 | completed | 962441.34 |
| Boomerang Textiles Pty Ltd | SO-2025-00873 | 2025-12-08 | completed | 418029.44 |
| Boomerang Textiles Pty Ltd | SO-2025-00867 | 2025-12-01 | completed | 33241.44 |
| Boomerang Textiles Pty Ltd | SO-2025-00713 | 2025-10-04 | completed | 470362.90 |

**结果摘要(代码生成,非 LLM)**:5 row(s) returned [customer_name, order_number, order_date, order_status, order_total_aud]. Top row: customer_name=Boomerang Textiles Pty Ltd, order_number=SO-2026-01137, order_date=2026-05-05, order_status=completed, order_total_aud=20335.38.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i01 | i01 |
| ✅ | 最终 SQL 含 `Boomerang Textiles` | - |
| ✅ | 结果非空(断言才测得到东西) | 5 |

#### E02 · 值改写(query) — ✅ 通过

**问题**:What's on order SO-2026-01270?

**① 检索**:i02 0.681 / i01 0.398 / i15 0.383 → 判定 `confident_hit`(top1 0.681,边距 0.283)  
命中的面:`What products are on SO-2026-01255 and how many units of each at what unit price?`(question)

**② 命中模板**:`i02` Query: Line items for an order number

**③ 计划**:feasible=`True`;输出 6 列 `o_order_number, o_product_sku, o_product_name, o_quantity, o_unit_sell_price_aud, o_line_amount_aud`;分组 `—`  
筛选:f_order_no="SO-2026-01270", f_is_active=null  

**④ 最终 SQL**

```sql
SELECT o.order_no AS order_number, p.sku AS product_sku, p.name AS product_name, oi.quantity AS quantity, oi.unit_price AS unit_sell_price_aud, oi.line_amount AS line_amount_aud FROM order_items AS oi JOIN orders AS o ON oi.order_id = o.id JOIN products AS p ON oi.product_id = p.id WHERE o.order_no = 'SO-2026-01270' AND p.is_active IN (0, 1) ORDER BY oi.id ASC LIMIT 50
```

**⑤ 执行**:1 行,列 `order_number, product_sku, product_name, quantity, unit_sell_price_aud, line_amount_aud`

| order_number | product_sku | product_name | quantity | unit_sell_price_aud | line_amount_aud |
| --- | --- | --- | --- | --- | --- |
| SO-2026-01270 | HC-215 | PowerCab HC-215 Battery Cabinet 215kWh | 1 | 147965.90 | 147965.90 |

**结果摘要(代码生成,非 LLM)**:1 row(s) returned [order_number, product_sku, product_name, quantity, unit_sell_price_aud, line_amount_aud]. Top row: order_number=SO-2026-01270, product_sku=HC-215, product_name=PowerCab HC-215 Battery Cabinet 215kWh, quantity=1, unit_sell_price_aud=147965.90, line_amount_aud=147965.90.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i02 | i02 |
| ✅ | 最终 SQL 含 `SO-2026-01270` | - |
| ✅ | 结果非空(断言才测得到东西) | 1 |

#### E03 · 值改写(query) — ✅ 通过

**问题**:Stock movement history for HC-300 at the Brisbane warehouse

**① 检索**:i15 0.764 / i18 0.587 / i16 0.587 → 判定 `confident_hit`(top1 0.764,边距 0.177)  
命中的面:`Can you show me the stock movement ledger for HC-300 at the Sydney warehouse for June 2026, with running balances?`(question)

**② 命中模板**:`i15` Query: Stock movement history for a product at a warehouse

**③ 计划**:feasible=`True`;输出 9 列 `o_product_sku, o_product_name, o_warehouse_name, o_movement_date, o_movement_type, o_quantity_moved, o_balance_after, o_source_reference, o_movement_id`;分组 `—`  
筛选:f_sku="%HC-300%", f_warehouse="Brisbane", f_movement_date_ge=null, f_movement_date_le=null  
> Mapped SKU fragment to %HC-300%.  
> Warehouse set to Brisbane.  
> Kept default date range 2024-09-01 to 2026-08-23.  

**④ 最终 SQL**

```sql
SELECT p.sku AS product_sku, p.name AS product_name, sm.warehouse AS warehouse_name, sm.movement_date AS movement_date, sm.movement_type AS movement_type, sm.quantity AS quantity_moved, sm.balance_after AS balance_after, sm.reference_no AS source_reference, sm.id AS movement_id FROM stock_movements AS sm JOIN products AS p ON sm.product_id = p.id WHERE p.sku LIKE '%HC-300%' AND sm.warehouse = 'Brisbane' AND sm.movement_date >= '2024-09-01' AND sm.movement_date <= '2026-08-23' ORDER BY sm.movement_date ASC, sm.id ASC LIMIT 50
```

**⑤ 执行**:21 行,列 `product_sku, product_name, warehouse_name, movement_date, movement_type, quantity_moved, balance_after, source_reference, movement_id`

| product_sku | product_name | warehouse_name | movement_date | movement_type | quantity_moved | balance_after | source_reference | movement_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | Brisbane | 2024-09-08 | inbound | 13 | 13 | GRN-2024-00018 | 260 |
| HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | Brisbane | 2024-10-16 | outbound | 7 | 6 | DO-2024-00023 | 261 |
| HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | Brisbane | 2024-11-12 | outbound | 1 | 5 | DO-2024-00024 | 262 |
| HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | Brisbane | 2024-12-01 | inbound | 25 | 30 | GRN-2024-00019 | 263 |
| HC-300 | PowerCab HC-300 Battery Cabinet 300kWh | Brisbane | 2025-01-23 | outbound | 6 | 24 | DO-2025-00077 | 264 |

**结果摘要(代码生成,非 LLM)**:21 row(s) returned [product_sku, product_name, warehouse_name, movement_date, movement_type, quantity_moved, balance_after, source_reference, movement_id]. Top row: product_sku=HC-300, product_name=PowerCab HC-300 Battery Cabinet 300kWh, warehouse_name=Brisbane, movement_date=2024-09-08, movement_type=inbound, quantity_moved=13, balance_after=13, source_reference=GRN-2024-00018, movement_id=260.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i15 | i15 |
| ✅ | 最终 SQL 含 `HC-300` | - |
| ✅ | 最终 SQL 含 `Brisbane` | - |
| ✅ | 结果非空(断言才测得到东西) | 21 |

#### E04 · 值改写(stats) — ✅ 通过

**问题**:Monthly revenue trend since January 2026

**① 检索**:i07 0.794 / i09 0.523 / i16 0.464 → 判定 `confident_hit`(top1 0.794,边距 0.272)  
命中的面:`Monthly revenue trend (excluding cancelled)`(summary)

**② 命中模板**:`i07` Stats: Monthly revenue trend (excluding cancelled)

**③ 计划**:feasible=`True`;输出 2 列 `o_month, o_total_revenue_aud`;分组 `g_month`  
筛选:f_order_date="2026-01-01", f_status=null  
> Interpreted "since January 2026" as start date 2026-01-01.  

**④ 最终 SQL**

```sql
SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month, SUM(o.total_amount) AS total_revenue_aud FROM orders AS o WHERE o.order_date >= '2026-01-01' AND o.status <> 'cancelled' GROUP BY DATE_FORMAT(o.order_date, '%Y-%m') ORDER BY month ASC LIMIT 200
```

**⑤ 执行**:8 行,列 `month, total_revenue_aud`

| month | total_revenue_aud |
| --- | --- |
| 2026-01 | 31262104.04 |
| 2026-02 | 21709415.09 |
| 2026-03 | 29324031.11 |
| 2026-04 | 10940769.54 |
| 2026-05 | 13186065.41 |

**结果摘要(代码生成,非 LLM)**:8 row(s) returned [month, total_revenue_aud]. Top row: month=2026-01, total_revenue_aud=31262104.04.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i07 | i07 |
| ✅ | 最终 SQL 含 `2026-01-01` | - |
| ✅ | 结果非空(断言才测得到东西) | 8 |

#### E05 · 值改写(stats) — ✅ 通过

**问题**:Monthly outbound units for Melbourne and Brisbane over the last 6 months

**① 检索**:i16 0.737 / i18 0.718 / i07 0.507 → 判定 `ambiguous_margin`(top1 0.737,边距 0.019,**边距不足,踩线过**)  
命中的面:`For Brisbane and Sydney, show monthly outbound movements by month since Jan 2026.`(question)

**② 命中模板**:`i16` Stats: Monthly outbound units trend by warehouse

**③ 计划**:feasible=`True`;输出 3 列 `o_year_month, o_warehouse_name, o_outbound_units`;分组 `g_year_month, g_warehouse_name`  
筛选:f_movement_date=["2026-02-23", "2026-08-23"], f_movement_type=null, f_warehouse=["Brisbane", "Melbourne"]  
> Resolved “last 6 months” to 2026-02-23 through 2026-08-23.  
> Warehouses limited to Brisbane and Melbourne.  

**④ 最终 SQL**

```sql
SELECT DATE_FORMAT(sm.movement_date, '%Y-%m') AS `year_month`, sm.warehouse AS `warehouse_name`, SUM(sm.quantity) AS `outbound_units` FROM stock_movements AS sm WHERE sm.movement_date BETWEEN '2026-02-23' AND '2026-08-23' AND sm.movement_type = 'outbound' AND sm.warehouse IN ('Brisbane', 'Melbourne') GROUP BY DATE_FORMAT(sm.movement_date, '%Y-%m'), sm.warehouse ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') ASC LIMIT 200
```

**⑤ 执行**:14 行,列 `year_month, warehouse_name, outbound_units`

| year_month | warehouse_name | outbound_units |
| --- | --- | --- |
| 2026-02 | Brisbane | 52 |
| 2026-02 | Melbourne | 569 |
| 2026-03 | Brisbane | 942 |
| 2026-03 | Melbourne | 827 |
| 2026-04 | Brisbane | 634 |

**结果摘要(代码生成,非 LLM)**:14 row(s) returned [year_month, warehouse_name, outbound_units]. Top row: year_month=2026-02, warehouse_name=Brisbane, outbound_units=52.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i16 | i16 |
| ✅ | 最终 SQL 含 `Melbourne` | - |
| ✅ | 最终 SQL 含 `Brisbane` | - |
| ✅ | 最终 SQL 不含 `Sydney` | - |
| ✅ | 结果非空(断言才测得到东西) | 14 |

#### E06 · 值改写(stats) — ✅ 通过

**问题**:Which products shipped the most units out of Sydney in the last 30 days?

**① 检索**:i18 0.821 / i16 0.635 / i15 0.570 → 判定 `confident_hit`(top1 0.821,边距 0.186)  
命中的面:`Top 5 products by outbound units from Sydney over the past three months.`(question)

**② 命中模板**:`i18` Stats: Top products by outbound units (last 90 days)

**③ 计划**:feasible=`True`;输出 4 列 `o_product_id, o_product_sku, o_product_name, o_total_outbound_units`;分组 `g_product_id, g_product_sku, g_product_name`  
筛选:f_movement_date="2026-07-25", f_movement_type=null, f_warehouse=["Sydney"]  
> Resolved 'last 30 days' to start date 2026-07-25 (through 2026-08-23).  
> Limited to Sydney warehouse as requested.  

**④ 最终 SQL**

```sql
SELECT p.id AS product_id, p.sku AS product_sku, p.name AS product_name, SUM(sm.quantity) AS total_outbound_units FROM stock_movements AS sm JOIN products AS p ON sm.product_id = p.id WHERE sm.movement_date >= '2026-07-25' AND sm.movement_type = 'outbound' AND sm.warehouse IN ('Sydney') GROUP BY p.id, p.sku, p.name ORDER BY total_outbound_units DESC LIMIT 10
```

**⑤ 执行**:8 行,列 `product_id, product_sku, product_name, total_outbound_units`

| product_id | product_sku | product_name | total_outbound_units |
| --- | --- | --- | --- |
| 16 | ACC-RACK | HC Series Mounting Rack Kit | 331 |
| 19 | ACC-METER | Smart Energy Meter 3-Phase | 208 |
| 18 | ACC-GATE | Monitoring Gateway G2 | 119 |
| 7 | INV-10K | SolarWave INV-10K String Inverter 10kW | 51 |
| 8 | INV-25K | SolarWave INV-25K String Inverter 25kW | 51 |

**结果摘要(代码生成,非 LLM)**:8 row(s) returned [product_id, product_sku, product_name, total_outbound_units]. Top row: product_id=16, product_sku=ACC-RACK, product_name=HC Series Mounting Rack Kit, total_outbound_units=331.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i18 | i18 |
| ✅ | 最终 SQL 含 `Sydney` | - |
| ✅ | 最终 SQL 不含 `Brisbane` | - |
| ✅ | 最终 SQL 不含 `Melbourne` | - |
| ✅ | 结果非空(断言才测得到东西) | 8 |

#### E07 · 值改写(stats) — ✅ 通过

**问题**:Who were our biggest customers by revenue in the past 6 months?

**① 检索**:i09 0.846 / i07 0.546 / i18 0.544 → 判定 `confident_hit`(top1 0.846,边距 0.300)  
命中的面:`Who were our 10 highest-revenue customers over the past 12 months?`(question)

**② 命中模板**:`i09` Stats: Top 10 customers by revenue (last 12 months)

**③ 计划**:feasible=`True`;输出 4 列 `o_customer_id, o_customer_name, o_total_revenue_aud, o_most_recent_order_date`;分组 `g_customer_id, g_customer_name`  
筛选:f_order_date="2026-02-23", f_status=null  
> Resolved "past 6 months" to 2026-02-23 through 2026-08-23.  
> Top 10 customers by revenue per template; ties broken by most recent order date.  

**④ 最终 SQL**

```sql
SELECT c.id AS customer_id, c.name AS customer_name, SUM(o.total_amount) AS total_revenue_aud, MAX(o.order_date) AS most_recent_order_date FROM orders AS o JOIN customers AS c ON o.customer_id = c.id WHERE o.order_date >= '2026-02-23' AND o.status <> 'cancelled' GROUP BY c.id, c.name ORDER BY total_revenue_aud DESC, most_recent_order_date DESC LIMIT 10
```

**⑤ 执行**:10 行,列 `customer_id, customer_name, total_revenue_aud, most_recent_order_date`

| customer_id | customer_name | total_revenue_aud | most_recent_order_date |
| --- | --- | --- | --- |
| 73 | Crestway Manufacturing Pty Ltd | 7490003.27 | 2026-08-06 |
| 9 | Redgum Logistics Pty Ltd | 6600570.39 | 2026-08-09 |
| 75 | Coastal Logistics Pty Ltd | 4525869.25 | 2026-06-10 |
| 70 | Granite Fabrication Pty Ltd | 4350912.87 | 2026-06-03 |
| 76 | Pacific Business Park Pty Ltd | 3785345.08 | 2026-08-09 |

**结果摘要(代码生成,非 LLM)**:10 row(s) returned [customer_id, customer_name, total_revenue_aud, most_recent_order_date]. Top row: customer_id=73, customer_name=Crestway Manufacturing Pty Ltd, total_revenue_aud=7490003.27, most_recent_order_date=2026-08-06.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i09 | i09 |
| ✅ | 结果非空(断言才测得到东西) | 10 |

#### E08 · 减列 — ✅ 通过

**问题**:For order SO-2026-01281 just show the product name and the quantity

**① 检索**:i02 0.782 / i01 0.410 / i15 0.372 → 判定 `confident_hit`(top1 0.782,边距 0.372)  
命中的面:`Give me all products on order SO-2026-01281 with their quantities and prices per unit.`(question)

**② 命中模板**:`i02` Query: Line items for an order number

**③ 计划**:feasible=`True`;输出 2 列 `o_product_name, o_quantity`;分组 `—`  
筛选:f_order_no="SO-2026-01281", f_is_active=null  

**④ 最终 SQL**

```sql
SELECT p.name AS product_name, oi.quantity AS quantity FROM order_items AS oi JOIN orders AS o ON oi.order_id = o.id JOIN products AS p ON oi.product_id = p.id WHERE o.order_no = 'SO-2026-01281' AND p.is_active IN (0, 1) ORDER BY oi.id ASC LIMIT 50
```

**⑤ 执行**:2 行,列 `product_name, quantity`

| product_name | quantity |
| --- | --- |
| Smart Energy Meter 3-Phase | 19 |
| Monitoring Gateway G2 | 26 |

**结果摘要(代码生成,非 LLM)**:2 row(s) returned [product_name, quantity]. Top row: product_name=Smart Energy Meter 3-Phase, quantity=19.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i02 | i02 |
| ✅ | 结果列含 `product_name` | product_name, quantity |
| ✅ | 结果列含 `quantity` | product_name, quantity |
| ✅ | 结果列不含 `unit_sell_price_aud` | product_name, quantity |
| ✅ | 结果列不含 `line_amount_aud` | product_name, quantity |
| ✅ | 结果非空(断言才测得到东西) | 2 |

#### E09 · 减列 — ✅ 通过

**问题**:Movement history for INV-110K at Sydney — only the movement date and the quantity, nothing else

**① 检索**:i15 0.588 / i16 0.458 / i02 0.400 → 判定 `confident_hit`(top1 0.588,边距 0.129)  
命中的面:`HC-215 Sydney stock movements since 2026-07-01`(question)

**② 命中模板**:`i15` Query: Stock movement history for a product at a warehouse

**③ 计划**:feasible=`True`;输出 2 列 `o_movement_date, o_quantity_moved`;分组 `—`  
筛选:f_sku="%INV-110K%", f_warehouse="Sydney", f_movement_date_ge=null, f_movement_date_le=null  
> Date range kept as default: 2024-09-01 to 2026-08-23  

**④ 最终 SQL**

```sql
SELECT sm.movement_date AS movement_date, sm.quantity AS quantity_moved FROM stock_movements AS sm JOIN products AS p ON sm.product_id = p.id WHERE p.sku LIKE '%INV-110K%' AND sm.warehouse = 'Sydney' AND sm.movement_date >= '2024-09-01' AND sm.movement_date <= '2026-08-23' ORDER BY sm.movement_date ASC, sm.id ASC LIMIT 50
```

**⑤ 执行**:23 行,列 `movement_date, quantity_moved`

| movement_date | quantity_moved |
| --- | --- |
| 2024-09-04 | 102 |
| 2024-10-07 | 21 |
| 2024-11-05 | 123 |
| 2024-11-26 | 53 |
| 2025-02-28 | -1 |

**结果摘要(代码生成,非 LLM)**:23 row(s) returned [movement_date, quantity_moved]. Top row: movement_date=2024-09-04, quantity_moved=102.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i15 | i15 |
| ✅ | 最终 SQL 含 `INV-110K` | - |
| ✅ | 最终 SQL 含 `Sydney` | - |
| ✅ | 结果列含 `movement_date` | movement_date, quantity_moved |
| ✅ | 结果列含 `quantity_moved` | movement_date, quantity_moved |
| ✅ | 结果列不含 `balance_after` | movement_date, quantity_moved |
| ✅ | 结果列不含 `source_reference` | movement_date, quantity_moved |
| ✅ | 结果列不含 `movement_id` | movement_date, quantity_moved |
| ✅ | 结果非空(断言才测得到东西) | 23 |

#### E10 · 减列 — ✅ 通过

**问题**:Recent orders for Pacific Dairy Co-op Pty Ltd — just the order number and the order total

**① 检索**:i01 0.790 / i07 0.547 / i02 0.545 → 判定 `confident_hit`(top1 0.790,边距 0.243)  
命中的面:`Customer: Pacific Dairy Co-op Pty Ltd — show orders from July 2026, exclude cancelled and pending.`(question)

**② 命中模板**:`i01` Query: Recent orders for a specific customer

**③ 计划**:feasible=`True`;输出 2 列 `o_order_number, o_order_total_aud`;分组 `—`  
筛选:f_name="%Pacific Dairy Co-op Pty Ltd%", f_order_date=null, f_status=null  
> Customer filter set to %Pacific Dairy Co-op Pty Ltd% (case-insensitive contains).  
> "Recent" interpreted as the template’s default start date 2025-08-23 (past 1 year up to 2026-08-23).  
> Statuses kept at default: completed, paid, pending, shipped.  

**④ 最终 SQL**

```sql
SELECT o.order_no AS order_number, o.total_amount AS order_total_aud FROM orders AS o JOIN customers AS c ON o.customer_id = c.id WHERE c.name LIKE '%Pacific Dairy Co-op Pty Ltd%' AND o.order_date >= '2025-08-23' AND o.status IN ('completed', 'paid', 'pending', 'shipped') ORDER BY o.order_date DESC, o.total_amount DESC LIMIT 50
```

**⑤ 执行**:10 行,列 `order_number, order_total_aud`

| order_number | order_total_aud |
| --- | --- |
| SO-2026-01221 | 47829.80 |
| SO-2026-01165 | 195525.72 |
| SO-2026-01144 | 194441.88 |
| SO-2026-01062 | 1594556.64 |
| SO-2026-00924 | 167156.67 |

**结果摘要(代码生成,非 LLM)**:10 row(s) returned [order_number, order_total_aud]. Top row: order_number=SO-2026-01221, order_total_aud=47829.80.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i01 | i01 |
| ✅ | 结果列含 `order_number` | order_number, order_total_aud |
| ✅ | 结果列含 `order_total_aud` | order_number, order_total_aud |
| ✅ | 结果列不含 `order_status` | order_number, order_total_aud |
| ✅ | 结果非空(断言才测得到东西) | 10 |

#### E11 · 减分组 — ✅ 通过

**问题**:Total outbound units per warehouse over the last 6 months, without the monthly breakdown

**① 检索**:i16 0.792 / i18 0.638 / i15 0.502 → 判定 `confident_hit`(top1 0.792,边距 0.153)  
命中的面:`Can you show monthly outbound units by warehouse for the last 12 months?`(question)

**② 命中模板**:`i16` Stats: Monthly outbound units trend by warehouse

**③ 计划**:feasible=`True`;输出 2 列 `o_warehouse_name, o_outbound_units`;分组 `g_warehouse_name`  
筛选:f_movement_date=["2026-02-23", "2026-08-23"], f_movement_type=null, f_warehouse=null  
> Resolved 'last 6 months' to 2026-02-23 through 2026-08-23.  
> Removed monthly breakdown as requested (aggregated totals per warehouse).  

**应用器裁剪/修正**:ORDER BY DATE_FORMAT(sm.movement_date, '%Y-%m') pruned (groupby dropped)

**④ 最终 SQL**

```sql
SELECT sm.warehouse AS `warehouse_name`, SUM(sm.quantity) AS `outbound_units` FROM stock_movements AS sm WHERE sm.movement_date BETWEEN '2026-02-23' AND '2026-08-23' AND sm.movement_type = 'outbound' AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney') GROUP BY sm.warehouse LIMIT 200
```

**⑤ 执行**:3 行,列 `warehouse_name, outbound_units`

| warehouse_name | outbound_units |
| --- | --- |
| Sydney | 5327 |
| Melbourne | 7076 |
| Brisbane | 5941 |

**结果摘要(代码生成,非 LLM)**:3 row(s) returned [warehouse_name, outbound_units]. Top row: warehouse_name=Sydney, outbound_units=5327.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i16 | i16 |
| ✅ | 结果列含 `warehouse_name` | warehouse_name, outbound_units |
| ✅ | 结果列含 `outbound_units` | warehouse_name, outbound_units |
| ✅ | 结果列不含 `year_month` | warehouse_name, outbound_units |
| ✅ | 结果非空(断言才测得到东西) | 3 |

#### E12 · 减分组 — ✅ 通过

**问题**:Units shipped in the last 90 days per SKU only — no product id, no product name

**① 检索**:i18 0.663 / i15 0.476 / i02 0.469 → 判定 `confident_hit`(top1 0.663,边距 0.187)  
命中的面:`Can you show top products by units shipped in the last 90 days?`(question)

**② 命中模板**:`i18` Stats: Top products by outbound units (last 90 days)

**③ 计划**:feasible=`True`;输出 2 列 `o_product_sku, o_total_outbound_units`;分组 `g_product_sku`  
筛选:f_movement_date=null, f_movement_type=null, f_warehouse=null  
> Resolved last 90 days as start date 2026-05-25 (anchored at 2026-08-23).  
> Per request, only SKU and units shown; product_id and product_name removed.  
> Warehouses kept at default: Brisbane, Melbourne, Sydney.  

**④ 最终 SQL**

```sql
SELECT p.sku AS product_sku, SUM(sm.quantity) AS total_outbound_units FROM stock_movements AS sm JOIN products AS p ON sm.product_id = p.id WHERE sm.movement_date >= '2026-05-25' AND sm.movement_type = 'outbound' AND sm.warehouse IN ('Brisbane', 'Melbourne', 'Sydney') GROUP BY p.sku ORDER BY total_outbound_units DESC LIMIT 10
```

**⑤ 执行**:10 行,列 `product_sku, total_outbound_units`

| product_sku | total_outbound_units |
| --- | --- |
| ACC-GATE | 1623 |
| ACC-METER | 1482 |
| ACC-RACK | 1395 |
| ACC-COOL | 1341 |
| ACC-CBL50 | 1123 |

**结果摘要(代码生成,非 LLM)**:10 row(s) returned [product_sku, total_outbound_units]. Top row: product_sku=ACC-GATE, total_outbound_units=1623.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i18 | i18 |
| ✅ | 结果列含 `product_sku` | product_sku, total_outbound_units |
| ✅ | 结果列含 `total_outbound_units` | product_sku, total_outbound_units |
| ✅ | 结果列不含 `product_id` | product_sku, total_outbound_units |
| ✅ | 结果列不含 `product_name` | product_sku, total_outbound_units |
| ✅ | 结果非空(断言才测得到东西) | 10 |

#### E13 · 减分组 — ✅ 通过

**问题**:What's our total revenue since January 2026 — one number, no monthly split

**① 检索**:i07 0.640 / i09 0.547 / i16 0.417 → 判定 `confident_hit`(top1 0.640,边距 0.093)  
命中的面:`Revenue by month since Jan 2026, paid orders only.`(question)

**② 命中模板**:`i07` Stats: Monthly revenue trend (excluding cancelled)

**③ 计划**:feasible=`True`;输出 1 列 `o_total_revenue_aud`;分组 `—`  
筛选:f_order_date="2026-01-01", f_status=null  
> Interpreted "since January 2026" as start date 2026-01-01  
> Dropped monthly grouping to return a single total  

**应用器裁剪/修正**:ORDER BY month pruned (column dropped)

**④ 最终 SQL**

```sql
SELECT SUM(o.total_amount) AS total_revenue_aud FROM orders AS o WHERE o.order_date >= '2026-01-01' AND o.status <> 'cancelled' LIMIT 200
```

**⑤ 执行**:1 行,列 `total_revenue_aud`

| total_revenue_aud |
| --- |
| 162851958.96 |

**结果摘要(代码生成,非 LLM)**:1 row(s) returned [total_revenue_aud]. Top row: total_revenue_aud=162851958.96.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = executed | executed |
| ✅ | 命中意图 = i07 | i07 |
| ✅ | 结果列含 `total_revenue_aud` | total_revenue_aud |
| ✅ | 结果列不含 `month` | total_revenue_aud |
| ✅ | 结果非空(断言才测得到东西) | 1 |

#### E14 · 模板外拒答 — ✅ 通过

**问题**:Monthly revenue broken down by product category

**① 检索**:i07 0.591 / i09 0.515 / i18 0.497 → 判定 `confident_hit`(top1 0.591,边距 0.076)  
命中的面:`Monthly revenue trend (excluding cancelled)`(summary)

**② 命中模板**:`i07` Stats: Monthly revenue trend (excluding cancelled)

**③ 计划**:feasible=`False`;输出 2 列 `o_month, o_total_revenue_aud`;分组 `g_month`  
筛选:f_order_date=null, f_status=null  
> Not feasible: Template has no product category column/group-by; cannot break down by category without adding a new dimension.  
> Kept default start date 2025-08-23; results cover available data through 2026-08-23.  
> Default exclusion of status = cancelled retained.  

**④ 最终 SQL**:未生成(拒答发生在生成之前)

**结果摘要(代码生成,非 LLM)**:Refused (refused_by_planner): Not feasible: Template has no product category column/group-by; cannot break down by category without adding a new dimension.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = refused_out_of_template | refused_out_of_template |
| ✅ | 未生成任何 SQL(拒答必须发生在生成之前) | - |

#### E15 · 模板外拒答 — ✅ 通过

**问题**:Top 10 customers by profit margin over the last 12 months

**① 检索**:i09 0.878 / i18 0.536 / i07 0.483 → 判定 `confident_hit`(top1 0.878,边距 0.343)  
命中的面:`Top 10 customers by revenue last 12 months`(question)

**② 命中模板**:`i09` Stats: Top 10 customers by revenue (last 12 months)

**③ 计划**:feasible=`False`;输出 4 列 `o_customer_id, o_customer_name, o_total_revenue_aud, o_most_recent_order_date`;分组 `g_customer_id, g_customer_name`  
筛选:f_order_date=null, f_status=null  
> User asked for ranking by profit margin, but this template only supports ranking by total revenue (AUD). Cannot add a profit margin metric or required columns/calculations.  
> "Last 12 months" resolved to 2025-08-23 to 2026-08-23; template default already matches this window.  

**④ 最终 SQL**:未生成(拒答发生在生成之前)

**结果摘要(代码生成,非 LLM)**:Refused (refused_by_planner): User asked for ranking by profit margin, but this template only supports ranking by total revenue (AUD). Cannot add a profit margin metric or required columns/calculations.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = refused_out_of_template | refused_out_of_template |
| ✅ | 命中意图 ∈ ['i09', 'i07'] | i09 |
| ✅ | 未生成任何 SQL(拒答必须发生在生成之前) | - |

#### E16 · 模板外拒答 — ✅ 通过

**问题**:Recent orders for Summit Manufacturing Pty Ltd plus the customer's phone number and credit limit

**① 检索**:i01 0.727 / i07 0.478 / i02 0.462 → 判定 `confident_hit`(top1 0.727,边距 0.249)  
命中的面:`Show me the most recent orders for Summit Manufacturing Pty Ltd over the last six months, excluding cancelled, with totals.`(question)

**② 命中模板**:`i01` Query: Recent orders for a specific customer

**③ 计划**:feasible=`False`;输出 5 列 `o_customer_name, o_order_number, o_order_date, o_order_status, o_order_total_aud`;分组 `—`  
筛选:f_name="%Summit Manufacturing Pty Ltd%", f_order_date=null, f_status=null  
> Infeasible: requested customer phone number and credit limit are not available in this template’s outputs; adding columns is outside planner powers.  
> Customer filter set to %Summit Manufacturing Pty Ltd%.  
> "Recent" left as the template default start date: 2025-08-23 (results cover 2025-08-23 to 2026-08-23).  

**④ 最终 SQL**:未生成(拒答发生在生成之前)

**结果摘要(代码生成,非 LLM)**:Refused (refused_by_planner): Infeasible: requested customer phone number and credit limit are not available in this template’s outputs; adding columns is outside planner powers.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = refused_out_of_template | refused_out_of_template |
| ✅ | 命中意图 ∈ ['i01'] | i01 |
| ✅ | 未生成任何 SQL(拒答必须发生在生成之前) | - |

#### E17 · 模板外拒答 — ✅ 通过

**问题**:Monthly outbound units by warehouse, but only for battery cabinet products

**① 检索**:i16 0.759 / i18 0.580 / i15 0.545 → 判定 `confident_hit`(top1 0.759,边距 0.179)  
命中的面:`Monthly outbound units trend by warehouse`(summary)

**② 命中模板**:`i16` Stats: Monthly outbound units trend by warehouse

**③ 计划**:feasible=`False`;输出 3 列 `o_year_month, o_warehouse_name, o_outbound_units`;分组 `g_year_month, g_warehouse_name`  
筛选:f_movement_date=null, f_movement_type=null, f_warehouse=null  
> Cannot filter to battery cabinet products: template has no product field/filter.  
> Kept default date range 2025-08-23 to 2026-08-23.  

**④ 最终 SQL**:未生成(拒答发生在生成之前)

**结果摘要(代码生成,非 LLM)**:Refused (refused_by_planner): Cannot filter to battery cabinet products: template has no product field/filter.

| 判 | 断言 | 实际 |
| --- | --- | --- |
| ✅ | 链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界) | - |
| ✅ | 路由 = text2sql | text2sql |
| ✅ | 终态 = refused_out_of_template | refused_out_of_template |
| ✅ | 命中意图 ∈ ['i16', 'i18'] | i16 |
| ✅ | 未生成任何 SQL(拒答必须发生在生成之前) | - |

#### E18 · 非问数拒答 — ✅ 通过

**问题**:What's the warranty period on the HC-300 battery cabinet?

**① 检索**:__non_data__ 0.579 / i15 0.518 / i02 0.261 → 判定 `null_route`(top1 0.579,边距 0.060)  
命中的面:`Does the HC series come with an extended warranty option?`(non_data)

**② 终态**:`refused_non_data` —— 未进入改写,零 LLM 调用。回给用户:*This does not look like a question I can answer from the business database. I can help with orders, customers, revenue and stock movement figures.*


#### E19 · 非问数拒答 — ✅ 通过

**问题**:How do I commission the INV-50K inverter on site?

**① 检索**:__non_data__ 0.584 / i15 0.376 / i02 0.314 → 判定 `null_route`(top1 0.584,边距 0.208)  
命中的面:`What is the operating temperature range of the INV-250K inverter?`(non_data)

**② 终态**:`refused_non_data` —— 未进入改写,零 LLM 调用。回给用户:*This does not look like a question I can answer from the business database. I can help with orders, customers, revenue and stock movement figures.*


#### E20 · 非问数拒答 — ✅ 通过

**问题**:Thanks, that's all for today.

**① 检索**:__non_data__ 0.299 / i15 0.194 / i02 0.186 → 判定 `null_route`(top1 0.299,边距 0.105)  
命中的面:`Good morning — how are you today?`(non_data)

**② 终态**:`refused_non_data` —— 未进入改写,零 LLM 调用。回给用户:*This does not look like a question I can answer from the business database. I can help with orders, customers, revenue and stock movement figures.*


---

## §3 机制披露

### 链路与四段埋点

```
用户问题
  ① retrieve   B7 双门槛:top1 ≥ 0.45 且 top1−top2 ≥ 0.03 → confident
               低于阈值 → refused_non_data(零 LLM 成本,交回 S4)
  ② plan       B6 LLM 单次产结构化计划(不写 SQL、不回灌重试)
               feasible=false → refused_out_of_template
  ③ apply      确定性应用器:未知 id 裁剪 / 非法值整体拒绝 / 分组联动 / AST 重建
  ④ execute    执行闸:单 SELECT、语义层白名单、LIMIT ≤ 500、15s 读超时
```

### 四个终态(定义在 `s3dev/pipeline.py`)

| 终态 | 谁判的 | 花几次 LLM |
| --- | --- | --- |
| `refused_non_data` | 检索层(向量阈值) | 0 |
| `refused_out_of_template` | planner 或应用器 | 1 |
| `executed` | 执行闸放行 | 1 |
| `execution_failed` | 数据库/执行闸报错 —— **永远算 bug** | 1 |

非问数拒答文案(面向用户,英文):*This does not look like a question I can answer from the business database. I can help with orders, customers, revenue and stock movement figures.*

### C5 要埋的 trace 事件形状(`pipeline.trace_events()` 现算)

```json
[
 {
  "stage": "retrieve_text2sql",
  "latency_ms": 3,
  "output": {
   "is_data_question": true,
   "confident": true,
   "top1_score": 0.8713,
   "margin": 0.3663,
   "candidates": [
    {
     "intent_id": "i01",
     "score": 0.8713
    },
    {
     "intent_id": "i07",
     "score": 0.505
    },
    {
     "intent_id": "i18",
     "score": 0.4946
    }
   ]
  }
 },
 {
  "stage": "rewrite_sql",
  "latency_ms": 6949,
  "output": {
   "template_id": "i01",
   "plan": {
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
      "value": "%Boomerang Textiles Pty Ltd%"
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
     "Using default start date 2025-08-23 since no specific date was requested.",
     "“Latest” is satisfied by existing ORDER BY (most recent first) and LIMIT 50."
    ]
   },
   "final_sql": "SELECT c.name AS customer_name, o.order_no AS order_number, o.order_date AS order_date, o.status AS order_status, o.total_amount AS order_total_aud FROM orders AS o JOIN customers AS c ON o.customer_id = c.id WHERE c.name LIKE '%Boomerang Textiles Pty Ltd%' AND o.order_date >= '2025-08-23' AND o.status IN ('completed', 'paid', 'pending', 'shipped') ORDER BY o.order_date DESC, o.total_amount DESC LIMIT 50",
   "violations": [],
   "adjustments": []
  }
 },
 {
  "stage": "execute_sql",
  "latency_ms": null,
  "output": {
   "sql_executed": "SELECT c.name AS customer_name, o.order_no AS order_n
```

### 断言字典(`verify()` 支持的 expect 键)

| 键 | 断言 |
| --- | --- |
| `route` | text2sql / fallback |
| `intent` | 命中意图精确等于 |
| `intent_in` | 命中意图属于集合(模板外拒答题不该把「最近模板」钉死) |
| `outcome` | 四个终态之一 |
| `sql_contains / sql_not_contains` | 最终 SQL 子串(大小写不敏感) |
| `cols_include / cols_exclude` | 结果列名精确成员判断 |
| `nonempty` | 结果行数 > 0(否则断言测不到东西) |
| `no_sql` | 未生成 SQL |
| `no_llm` | 未产生计划 = 一次 LLM 都没花 |

### 产物

| 文件 | 内容 |
| --- | --- |
| `out/eval_cases.json` | 评测集(手写,回归资产,人可增删改) |
| `out/e2e_cases/*.json` | 逐题全链路产物(检索/计划/SQL/结果/断言) |
| `out/e2e_eval.json` | 汇总:全部结果 + 统计 |
| `out/B8-REVIEW.md` | 本报告(全部数字由代码现算渲染) |

### 复跑
```bash
uv run python run_b8_e2e.py --all     # 真调 LLM,测今天这条链路
uv run python run_b8_e2e.py --check   # 免费复验:重放已存计划 + 重跑断言(确定性)
```
