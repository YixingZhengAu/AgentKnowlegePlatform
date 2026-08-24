# B1 SchemaSnapshot 评审报告 — `demo_biz`

生成时间:2026-08-23T06:01:46+00:00 · 表数:7 · 关系数:6

## 表间关系

| 从 | 到 | 来源 |
|---|---|---|
| order_items.order_id | orders.id | FK |
| order_items.product_id | products.id | FK |
| orders.customer_id | customers.id | FK |
| stock_movements.product_id | products.id | FK |
| inventory.product_id | products.id | **列名启发(需人工确认)** |
| orders.sales_rep_id | sales_reps.id | **列名启发(需人工确认)** |

## `customers`(80 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 80 |  | 1, 2, 3, 4, 5 |  |
| name | varchar(128) |  |  | 80 |  | Bluegum Beverages Pty Ltd, Bluegum Business Park Pty Ltd, Bluegum Dairy Co-op Pty Ltd, Bluegum Engineering Pty Ltd, Bluegum Food Processing Pty Ltd |  |
| state | varchar(3) | MUL |  | 5 | NSW, QLD, SA, VIC, WA | NSW, QLD, SA, VIC, WA | Australian state: NSW / VIC / QLD / SA / WA |
| channel_type | varchar(16) |  |  | 2 | direct, distributor | direct, distributor |  |
| industry | varchar(32) |  |  | 5 | agriculture, commercial_complex, factory, industrial_park, logistics | agriculture, commercial_complex, factory, industrial_park, logistics |  |
| created_at | date |  |  | 77 |  | 2023-01-04, 2023-01-29, 2023-02-09, 2023-02-12, 2023-03-12 |  |

## `inventory`(60 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 60 |  | 1, 2, 3, 4, 5 |  |
| product_id | int unsigned | MUL |  | 20 |  | 1, 2, 3, 4, 5 |  |
| warehouse | varchar(32) |  |  | 3 | Brisbane, Melbourne, Sydney | Brisbane, Melbourne, Sydney | Warehouse city: Sydney / Melbourne / Brisbane |
| on_hand_qty | int |  |  | 51 |  | 4, 7, 8, 14, 15 |  |
| reserved_qty | int |  |  | 31 |  | 0, 1, 2, 3, 4 |  |
| updated_at | datetime |  |  | 60 |  | 2026-05-04T11:19:00, 2026-05-09T09:35:00, 2026-06-04T09:08:00, 2026-06-05T08:54:00, 2026-06-14T15:03:00 |  |

## `order_items`(2613 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 2613 |  | 1, 2, 3, 4, 5 |  |
| order_id | int unsigned | MUL |  | 1289 |  | 1, 2, 3, 4, 5 |  |
| product_id | int unsigned | MUL |  | 20 |  | 1, 2, 3, 4, 5 |  |
| quantity | int unsigned |  |  | 30 |  | 1, 2, 3, 4, 5 |  |
| unit_price | decimal(12,2) |  |  | 2609 |  | 312.95, 312.98, 313.10, 313.16, 314.24 | Actual sell price per unit in AUD after discount (may differ from list price) |
| line_amount | decimal(14,2) |  |  | 2611 |  | 652.98, 696.72, 734.62, 741.84, 987.24 |  |

## `orders`(1289 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 1289 |  | 1, 2, 3, 4, 5 |  |
| order_no | varchar(20) | UNI |  | 1289 |  | SO-2024-00001, SO-2024-00002, SO-2024-00003, SO-2024-00004, SO-2024-00005 | Business order number, e.g. SO-2025-00123 |
| customer_id | int unsigned | MUL |  | 80 |  | 1, 2, 3, 4, 5 |  |
| sales_rep_id | int unsigned |  |  | 15 |  | 1, 2, 3, 4, 5 |  |
| order_date | date | MUL |  | 587 |  | 2024-09-01, 2024-09-02, 2024-09-03, 2024-09-04, 2024-09-05 |  |
| status | varchar(16) | MUL |  | 5 | cancelled, completed, paid, pending, shipped | cancelled, completed, paid, pending, shipped |  |
| total_amount | decimal(14,2) |  |  | 1289 |  | 734.62, 987.24, 1744.45, 2268.88, 2499.91 | Order total in AUD, equals the sum of its line amounts |

## `products`(20 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 20 |  | 1, 2, 3, 4, 5 |  |
| sku | varchar(32) | UNI |  | 20 |  | ACC-CBL50, ACC-COOL, ACC-GATE, ACC-METER, ACC-RACK | Product SKU, e.g. HC-215 |
| name | varchar(128) |  |  | 20 |  | DC Cable Kit 50m, GridMind EMS Enterprise Licence, GridMind EMS Lite Licence, GridMind EMS Pro Licence, HC Series HVAC Cooling Module |  |
| series | varchar(8) |  |  | 4 | ACC, EMS, HC, INV | ACC, EMS, HC, INV | Product series: HC (battery cabinet) / INV (inverter) / EMS (energy mgmt system) / ACC (accessory) |
| category | varchar(32) |  |  | 4 | accessory, battery_cabinet, ems_software, inverter | accessory, battery_cabinet, ems_software, inverter |  |
| unit_price | decimal(12,2) |  |  | 20 |  | 380.00, 640.00, 920.00, 1450.00, 3200.00 | List price in AUD, ex GST |
| launch_date | date |  |  | 13 |  | 2022-06-01, 2023-01-10, 2023-02-01, 2023-05-01, 2023-08-01 |  |
| is_active | tinyint(1) |  |  | 1 | 1 | 1 |  |

## `sales_reps`(15 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 15 |  | 1, 2, 3, 4, 5 |  |
| name | varchar(64) |  |  | 15 |  | Ava Patel, Ethan Zhang, Grace Taylor, Harper Singh, Isla Martin |  |
| state | varchar(3) |  |  | 5 | NSW, QLD, SA, VIC, WA | NSW, QLD, SA, VIC, WA |  |
| team | varchar(16) |  |  | 2 | channel, direct | channel, direct | direct = own sales team, channel = distributor manager |
| hired_date | date |  |  | 15 |  | 2021-04-13, 2021-06-08, 2021-09-06, 2021-11-22, 2022-04-26 |  |
| is_active | tinyint(1) |  |  | 1 | 1 | 1 |  |

## `stock_movements`(1373 行)
表注释:_(无)_

| 列 | 类型 | 键 | 可空 | distinct | 枚举取值 | 采样 | 注释 |
|---|---|---|---|---|---|---|---|
| id | int unsigned | PRI |  | 1373 |  | 1, 2, 3, 4, 5 |  |
| product_id | int unsigned | MUL |  | 20 |  | 1, 2, 3, 4, 5 |  |
| warehouse | varchar(32) |  |  | 3 | Brisbane, Melbourne, Sydney | Brisbane, Melbourne, Sydney |  |
| movement_type | varchar(16) |  |  | 3 | adjustment, inbound, outbound | adjustment, inbound, outbound |  |
| quantity | int |  |  | 350 |  | -3, -2, -1, 1, 2 | Units moved; positive for inbound/outbound (direction given by movement_type), signed for adjustment |
| balance_after | int |  |  | 495 |  | 0, 2, 3, 4, 5 | On-hand quantity in this warehouse right after this movement (running balance) |
| movement_date | date | MUL |  | 580 |  | 2024-09-01, 2024-09-02, 2024-09-03, 2024-09-04, 2024-09-05 |  |
| reference_no | varchar(24) |  | Y | 1302 |  | DO-2024-00001, DO-2024-00002, DO-2024-00003, DO-2024-00004, DO-2024-00005 | Source document: GRN-yyyy-nnnnn goods receipt, DO-yyyy-nnnnn delivery order; NULL for stocktake adjustments |
