# B2 语义层评审报告

- 库:`demo_biz`,生成于 2026-08-23T16:09:51
- **审核要点**:不看数据的人能否凭 description 正确理解字段;枚举逐值解释是否符合业务;
  原注释列(fill 模式下逐字保留)与 AI 生成列(**加粗标出**)是否风格一致。

## `customers`(mode=fill)

**表描述**:Each row represents a customer account in Australia that the company sells to or through. The table stores customer identity, location (state), sales channel, industry segment, and the date the account was created. It links to orders so sales can be attributed to the correct customer.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Customer ID | **System-generated unique identifier for the customer account. Referenced by orders.customer_id to link each order to this customer.** |
| `name` | varchar(128) | Bluegum Beverages Pty Ltd, Bluegum Business Park Pty Ltd, Bluegum Dairy Co-op Pty Ltd | — | Customer Name | **Legal or trading name of the customer, as stored in the CRM/ERP. Text up to 128 characters.** |
| `state` | varchar(3) | NSW, QLD, SA | Australian state: NSW / VIC / QLD / SA / WA | State | Australian state: NSW / VIC / QLD / SA / WA |
| `channel_type` | varchar(16) | direct, distributor | — | Channel Type | **Sales channel relationship for this customer account. Indicates whether the company sells to this account directly or via distribution.** |
| `industry` | varchar(32) | agriculture, commercial_complex, factory | — | Industry | **Primary industry segment for the customer account. Used for segmentation and reporting.** |
| `created_at` | date | 2023-01-04, 2023-01-29, 2023-02-09 | — | Created Date | **Date the customer record was created/onboarded (YYYY‑MM‑DD, day-level). Useful for cohorting and account age analysis.** |

**枚举逐值解释(全部 AI 生成)**:

- `state`:
  - `NSW` — New South Wales.
  - `QLD` — Queensland.
  - `SA` — South Australia.
  - `VIC` — Victoria.
  - `WA` — Western Australia.
- `channel_type`:
  - `direct` — The company sells directly to this customer (end account).
  - `distributor` — The customer is a distributor/reseller purchasing for onward sale.
- `industry`:
  - `agriculture` — Farms and agricultural producers or agribusiness operations.
  - `commercial_complex` — Shopping centres, office parks, or mixed-use commercial complexes.
  - `factory` — Manufacturing plants and production facilities.
  - `industrial_park` — Multi-tenant industrial estates or business parks.
  - `logistics` — Warehousing, distribution, and freight/logistics operators.

## `inventory`(mode=fill)

**表描述**:Current inventory by product and warehouse. Each row represents the latest stock position for one product at one company warehouse location, including on-hand and reserved quantities.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Inventory ID | **Surrogate primary key for this inventory row. Uniquely identifies the product–warehouse stock record.** |
| `product_id` | int unsigned | 1, 2, 3 | — | Product | **References products.id; identifies which product this stock row is for. Join to Products to get SKU, name, series, category, and pricing details.** |
| `warehouse` | varchar(32) | Brisbane, Melbourne, Sydney | Warehouse city: Sydney / Melbourne / Brisbane | Warehouse | Warehouse city: Sydney / Melbourne / Brisbane |
| `on_hand_qty` | int | 4, 7, 8 | — | On-hand Quantity | **Integer count of units physically on hand at the warehouse at the last update. Represents the total stock present, in whole units (no partials).** |
| `reserved_qty` | int | 0, 1, 2 | — | Reserved Quantity | **Integer count of units allocated to open orders and therefore not available for new allocation. Represents a subset of on-hand stock that is reserved until released or shipped.** |
| `updated_at` | datetime | 2026-05-04T11:19:00, 2026-05-09T09:35:00, 2026-06-04T09:08:00 | — | Last Updated | **Timestamp when the quantities were last refreshed for this product and warehouse. Datetime in ISO 8601 format (YYYY-MM-DDThh:mm:ss), to the minute/second precision.** |

**枚举逐值解释(全部 AI 生成)**:

- `warehouse`:
  - `Brisbane` — Stock stored in the Brisbane warehouse.
  - `Melbourne` — Stock stored in the Melbourne warehouse.
  - `Sydney` — Stock stored in the Sydney warehouse.

## `order_items`(mode=fill)

**表描述**:One row represents a single line item on a customer order. It records which product was sold on the order, the quantity, the actual per‑unit sell price in AUD after discounts, and the extended line amount.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Line Item ID | **Unique identifier for the order line item. One row per product line on an order.** |
| `order_id` | int unsigned | 1, 2, 3 | — | Order ID | **References orders.id; links this line item to the specific customer order it belongs to.** |
| `product_id` | int unsigned | 1, 2, 3 | — | Product ID | **References products.id; identifies the specific product (SKU) sold on this line.** |
| `quantity` | int unsigned | 1, 2, 3 | — | Quantity | **Number of units of the product on this line, as defined by the product’s selling unit. Whole number (no decimals).** |
| `unit_price` | decimal(12,2) | 312.95, 312.98, 313.10 | Actual sell price per unit in AUD after discount (may differ from list price) | Unit Price AUD | Actual sell price per unit in AUD after discount (may differ from list price) |
| `line_amount` | decimal(14,2) | 652.98, 696.72, 734.62 | — | Line Amount AUD | **Extended line total in AUD, typically quantity × unit_price. Stored as decimal with two decimal places.** |

## `orders`(mode=fill)

**表描述**:One row represents a single customer sales order placed with the company. The table tracks who the customer and sales rep are, the order date and status, and the total order value in AUD; detailed products are stored in order_items.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Order ID | **System-generated primary key for the order. Used to join to order_items.order_id.** |
| `order_no` | varchar(20) | SO-2024-00001, SO-2024-00002, SO-2024-00003 | Business order number, e.g. SO-2025-00123 | Order Number | Business order number, e.g. SO-2025-00123 |
| `customer_id` | int unsigned | 1, 2, 3 | — | Customer ID | **References customers.id, linking the order to the purchasing customer. Use to join and retrieve customer details such as name, state, and industry.** |
| `sales_rep_id` | int unsigned | 1, 2, 3 | — | Sales Rep ID | **References sales_reps.id, indicating the sales representative responsible for the order. Use to join for rep name, team, and territory details.** |
| `order_date` | date | 2024-09-01, 2024-09-02, 2024-09-03 | — | Order Date | **Calendar date the order was created, stored as YYYY-MM-DD (day-level granularity). Used for booking and time-based reporting.** |
| `status` | varchar(16) | cancelled, completed, paid | — | Order Status | **Current lifecycle state of the order. Used to track processing, fulfillment, and closure.** |
| `total_amount` | decimal(14,2) | 734.62, 987.24, 1744.45 | Order total in AUD, equals the sum of its line amounts | Order Total | Order total in AUD, equals the sum of its line amounts |

**枚举逐值解释(全部 AI 生成)**:

- `status`:
  - `cancelled` — Order was voided and will not be fulfilled or invoiced further.
  - `completed` — Order has been fully fulfilled and closed out.
  - `paid` — Payment has been received for the order.
  - `pending` — Order has been created and is awaiting further processing (e.g., payment or fulfillment).
  - `shipped` — Goods have been dispatched to the customer.

## `products`(mode=fill)

**表描述**:One row represents a distinct product that the company sells, including hardware and software such as mounting accessories, inverters, battery cabinets, and EMS licenses. The table stores identifiers, classification (series/category), list price in AUD (ex GST), launch date, and whether the product is active.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Product ID | **Surrogate primary key for the product. Referenced by order_items.product_id, inventory.product_id, and stock_movements.product_id to link line items and stock to this product.** |
| `sku` | varchar(32) | ACC-CBL50, ACC-COOL, ACC-GATE | Product SKU, e.g. HC-215 | SKU | Product SKU, e.g. HC-215 |
| `name` | varchar(128) | DC Cable Kit 50m, GridMind EMS Enterprise Licence, GridMind EMS Lite Licence | — | Product Name | **Human-readable product name up to 128 characters. Used on customer documents and internal listings.** |
| `series` | varchar(8) | ACC, EMS, HC | Product series: HC (battery cabinet) / INV (inverter) / EMS (energy mgmt system) / ACC (accessory) | Product Series | Product series: HC (battery cabinet) / INV (inverter) / EMS (energy mgmt system) / ACC (accessory) |
| `category` | varchar(32) | accessory, battery_cabinet, ems_software | — | Product Category | **Business category used for reporting and pricing segmentation.** |
| `unit_price` | decimal(12,2) | 380.00, 640.00, 920.00 | List price in AUD, ex GST | List Price (AUD) | List price in AUD, ex GST |
| `launch_date` | date | 2022-06-01, 2023-01-10, 2023-02-01 | — | Launch Date | **Date the product was launched to market (YYYY-MM-DD, day-level granularity). Useful for cohorting and lifecycle analysis.** |
| `is_active` | tinyint(1) | 1 | — | Active Flag | **Indicates whether the product is currently active/for sale; stored as tinyint(1). Value 1 appears for active products in the data.** |

**枚举逐值解释(全部 AI 生成)**:

- `series`:
  - `ACC` — Accessory products and add-on kits related to the core systems.
  - `EMS` — Energy management system products (GridMind EMS platform).
  - `HC` — HC battery cabinet hardware line.
  - `INV` — Power inverter product line.
- `category`:
  - `accessory` — Ancillary parts and kits that complement core products.
  - `battery_cabinet` — Battery cabinet hardware (primarily HC series).
  - `ems_software` — GridMind EMS software licenses/editions.
  - `inverter` — AC power inverter units.
- `is_active`:
  - `1` — Product is active and available for sale.

## `sales_reps`(mode=fill)

**表描述**:One row represents a sales representative employed by the company in Australia. The table records each rep’s name, base state, team type, hire date, and active status, and is referenced by orders via sales_rep_id.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Rep ID | **Unique identifier for the sales representative. Referenced by orders.sales_rep_id to attribute orders to the responsible rep.** |
| `name` | varchar(64) | Ava Patel, Ethan Zhang, Grace Taylor | — | Full Name | **Sales representative’s full name (first and last). Text up to 64 characters.** |
| `state` | varchar(3) | NSW, QLD, SA | — | State | **Three-letter Australian state code indicating the rep’s base location.** |
| `team` | varchar(16) | channel, direct | direct = own sales team, channel = distributor manager | Sales Team | direct = own sales team, channel = distributor manager |
| `hired_date` | date | 2021-04-13, 2021-06-08, 2021-09-06 | — | Hire Date | **Date the rep started employment. Date format YYYY-MM-DD (day-level granularity).** |
| `is_active` | tinyint(1) | 1 | — | Active Flag | **Boolean-like flag indicating if the rep is currently active on staff. Stored as tinyint(1).** |

**枚举逐值解释(全部 AI 生成)**:

- `state`:
  - `NSW` — New South Wales.
  - `QLD` — Queensland.
  - `SA` — South Australia.
  - `VIC` — Victoria.
  - `WA` — Western Australia.
- `team`:
  - `channel` — Rep manages distributor/channel partner relationships.
  - `direct` — Rep belongs to the in-house direct sales team handling end-customer accounts.
- `is_active`:
  - `1` — Rep is currently active.

## `stock_movements`(mode=fill)

**表描述**:Each row records a single inventory movement for a specific product at a specific warehouse. It captures inbound, outbound, and adjustment events, the quantity moved, the resulting on‑hand balance, the movement date, and the source document reference.

| 列 | 类型 | 采样 | 原注释 | display_name | description |
|---|---|---|---|---|---|
| `id` | int unsigned | 1, 2, 3 | — | Movement ID | **System-generated unique identifier for the stock movement record. Use this to reference a specific ledger entry.** |
| `product_id` | int unsigned | 1, 2, 3 | — | Product | **Links to products.id; identifies which product the stock movement is for. Join to Products to see SKU, name, and other product details.** |
| `warehouse` | varchar(32) | Brisbane, Melbourne, Sydney | — | Warehouse | **Warehouse where the movement occurred. Values indicate the physical warehouse location by city.** |
| `movement_type` | varchar(16) | adjustment, inbound, outbound | — | Movement Type | **Categorizes the movement as inbound, outbound, or an adjustment. Used together with quantity to determine stock increase or decrease.** |
| `quantity` | int | -3, -2, -1 | Units moved; positive for inbound/outbound (direction given by movement_type), signed for adjustment | Quantity Moved | Units moved; positive for inbound/outbound (direction given by movement_type), signed for adjustment |
| `balance_after` | int | 0, 2, 3 | On-hand quantity in this warehouse right after this movement (running balance) | Balance After | On-hand quantity in this warehouse right after this movement (running balance) |
| `movement_date` | date | 2024-09-01, 2024-09-02, 2024-09-03 | — | Movement Date | **Calendar date of the movement (YYYY‑MM‑DD, day-level granularity).** |
| `reference_no` | varchar(24) | DO-2024-00001, DO-2024-00002, DO-2024-00003 | Source document: GRN-yyyy-nnnnn goods receipt, DO-yyyy-nnnnn delivery order; NULL for stocktake adjustments | Source Reference | Source document: GRN-yyyy-nnnnn goods receipt, DO-yyyy-nnnnn delivery order; NULL for stocktake adjustments |

**枚举逐值解释(全部 AI 生成)**:

- `warehouse`:
  - `Brisbane` — Movement occurred at the Brisbane warehouse.
  - `Melbourne` — Movement occurred at the Melbourne warehouse.
  - `Sydney` — Movement occurred at the Sydney warehouse.
- `movement_type`:
  - `inbound` — Stock received into the warehouse (e.g., purchase receipt or transfer-in).
  - `outbound` — Stock dispatched from the warehouse (e.g., customer delivery or transfer-out).
  - `adjustment` — Manual correction from stocktake or error correction; can increase or decrease stock.
