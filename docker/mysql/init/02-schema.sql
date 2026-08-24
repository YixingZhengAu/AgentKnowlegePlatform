-- demo_biz 六表 DDL。
-- 设计意图(对应 S3-PLAN A1/B1):
--   * 列注释故意只覆盖一部分 —— B2 的 description 生成必须能从列名/采样值推断,不能依赖注释齐全
--   * orders.sales_rep_id 与 inventory.product_id 故意不建 FK —— 验证 B1 对"无外键的逻辑关联"的兜底
--   * 低基数维度(state/status/...)用 VARCHAR 而非 ENUM —— 逼 B1 走"distinct 采样"识别枚举,更接近真实客户库
USE demo_biz;

CREATE TABLE products (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sku           VARCHAR(32)      NOT NULL UNIQUE COMMENT 'Product SKU, e.g. HC-215',
  name          VARCHAR(128)     NOT NULL,
  series        VARCHAR(8)       NOT NULL COMMENT 'Product series: HC (battery cabinet) / INV (inverter) / EMS (energy mgmt system) / ACC (accessory)',
  category      VARCHAR(32)      NOT NULL,
  unit_price    DECIMAL(12,2)    NOT NULL COMMENT 'List price in AUD, ex GST',
  launch_date   DATE             NOT NULL,
  is_active     TINYINT(1)       NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE customers (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(128)     NOT NULL,
  state         VARCHAR(3)       NOT NULL COMMENT 'Australian state: NSW / VIC / QLD / SA / WA',
  channel_type  VARCHAR(16)      NOT NULL,
  industry      VARCHAR(32)      NOT NULL,
  created_at    DATE             NOT NULL,
  KEY idx_customers_state (state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sales_reps (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(64)      NOT NULL,
  state         VARCHAR(3)       NOT NULL,
  team          VARCHAR(16)      NOT NULL COMMENT 'direct = own sales team, channel = distributor manager',
  hired_date    DATE             NOT NULL,
  is_active     TINYINT(1)       NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE orders (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_no      VARCHAR(20)      NOT NULL UNIQUE COMMENT 'Business order number, e.g. SO-2025-00123',
  customer_id   INT UNSIGNED     NOT NULL,
  sales_rep_id  INT UNSIGNED     NOT NULL,
  order_date    DATE             NOT NULL,
  status        VARCHAR(16)      NOT NULL,
  total_amount  DECIMAL(14,2)    NOT NULL COMMENT 'Order total in AUD, equals the sum of its line amounts',
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id),
  KEY idx_orders_date (order_date),
  KEY idx_orders_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_items (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_id      INT UNSIGNED     NOT NULL,
  product_id    INT UNSIGNED     NOT NULL,
  quantity      INT UNSIGNED     NOT NULL,
  unit_price    DECIMAL(12,2)    NOT NULL COMMENT 'Actual sell price per unit in AUD after discount (may differ from list price)',
  line_amount   DECIMAL(14,2)    NOT NULL,
  CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders(id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id),
  KEY idx_items_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE inventory (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id    INT UNSIGNED     NOT NULL,
  warehouse     VARCHAR(32)      NOT NULL COMMENT 'Warehouse city: Sydney / Melbourne / Brisbane',
  on_hand_qty   INT              NOT NULL,
  reserved_qty  INT              NOT NULL DEFAULT 0,
  updated_at    DATETIME         NOT NULL,
  UNIQUE KEY uq_inventory (product_id, warehouse)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 库存流水:inventory 是"现在有多少"的快照,这张表是"怎么变成这样"的过程,
-- 让库存侧具备时间维度(月度出入库、流水明细、盘点调整)。
-- 设计:movement_type 故意不写注释(逼 B2 从枚举取值推断);quantity 对 adjustment 可为负。
CREATE TABLE stock_movements (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id    INT UNSIGNED     NOT NULL,
  warehouse     VARCHAR(32)      NOT NULL,
  movement_type VARCHAR(16)      NOT NULL,
  quantity      INT              NOT NULL COMMENT 'Units moved; positive for inbound/outbound (direction given by movement_type), signed for adjustment',
  balance_after INT              NOT NULL COMMENT 'On-hand quantity in this warehouse right after this movement (running balance)',
  movement_date DATE             NOT NULL,
  reference_no  VARCHAR(24)      NULL COMMENT 'Source document: GRN-yyyy-nnnnn goods receipt, DO-yyyy-nnnnn delivery order; NULL for stocktake adjustments',
  CONSTRAINT fk_movements_product FOREIGN KEY (product_id) REFERENCES products(id),
  KEY idx_movements_date (movement_date),
  KEY idx_movements_prod_wh (product_id, warehouse)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
