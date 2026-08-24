"""业务库自检:对演示业务库 demo_biz 逐项断言(S3-PLAN A1 的通过标准,C2 迁到正式路径)。

跑法:`make bizdb-verify`(= `cd server && uv run python -m scripts.verify_bizdb`)。
全绿输出 "BIZDB VERIFY: ALL PASS";任一项 FAIL 退出码非 0(bootstrap.sh 会因此中断)。

**为什么演示数据值得一份 27 项的断言脚本**:问数的每一个演示答案都是从这些数里算出来的。
数据里一处形状不对(某个月没单、订单头总额与行不一致、库存快照与流水对不上),
症状不会是"数据不对",而是"AI 算错了" —— 那是最难查的一类假问题。
最后一项断言的是只读账号写入被拒:安全闸的第一道在数据库权限上,不在代码里。
"""

from __future__ import annotations

import sys

import pymysql

from app.services.text2sql.bizdb import connect, demo_conn

FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


def main() -> None:
    conn = connect(demo_conn(), timeout=30)
    cur = conn.cursor()
    # 1. 七表齐全
    cur.execute("SHOW TABLES")
    tables = {r[0] for r in cur.fetchall()}
    expected = {"products", "customers", "sales_reps", "orders", "order_items", "inventory",
                "stock_movements"}
    check("seven tables present", tables == expected, f"got {sorted(tables)}")

    # 2. 行数达标
    mins = {"products": 15, "customers": 80, "sales_reps": 15,
            "orders": 1000, "order_items": 2000, "inventory": 60, "stock_movements": 800}
    for t, lo in mins.items():
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        check(f"{t} rows >= {lo}", n >= lo, f"n={n}")

    # 3. 订单头总额 = 行聚合(全量核对,不止抽 20 单)
    cur.execute("""
        SELECT COUNT(*) FROM orders o
        JOIN (SELECT order_id, SUM(line_amount) s FROM order_items GROUP BY order_id) i
          ON i.order_id = o.id
        WHERE ABS(o.total_amount - i.s) > 0.01""")
    check("orders.total_amount == sum(items)", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM orders o LEFT JOIN order_items i ON i.order_id=o.id "
                "WHERE i.id IS NULL")
    check("every order has items", cur.fetchone()[0] == 0)

    # 4. 日期覆盖:近 24 个月每月都有单
    cur.execute("SELECT DATE_FORMAT(order_date,'%Y-%m'), COUNT(*) FROM orders "
                "GROUP BY 1 ORDER BY 1")
    rows = cur.fetchall()
    check("24 distinct months", len(rows) == 24,
          f"months={len(rows)} range={rows[0][0]}..{rows[-1][0]}")
    check("every month has orders", all(r[1] > 0 for r in rows))

    # 5. 五个州都有客户与订单
    cur.execute("SELECT COUNT(DISTINCT state) FROM customers")
    check("5 states in customers", cur.fetchone()[0] == 5)
    cur.execute("SELECT COUNT(DISTINCT c.state) FROM orders o "
                "JOIN customers c ON c.id=o.customer_id")
    check("5 states in orders", cur.fetchone()[0] == 5)

    # 6. cancelled 占比在 3%–12%
    cur.execute("SELECT AVG(status='cancelled') FROM orders")
    ratio = float(cur.fetchone()[0])
    check("cancelled ratio 3%-12%", 0.03 <= ratio <= 0.12, f"{ratio:.1%}")

    # 7. 引用完整性(含故意没建 FK 的两条逻辑关联)
    cur.execute("SELECT COUNT(*) FROM orders o LEFT JOIN sales_reps r ON r.id=o.sales_rep_id "
                "WHERE r.id IS NULL")
    check("orders.sales_rep_id all valid (no FK)", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM inventory v LEFT JOIN products p ON p.id=v.product_id "
                "WHERE p.id IS NULL")
    check("inventory.product_id all valid (no FK)", cur.fetchone()[0] == 0)

    # 8. 库存流水:快照 = 流水净额(全量 60 组合核对);滚动余额任意时点不为负;
    #    类型取值合法;上市前无流水;近月覆盖
    cur.execute("""
        SELECT COUNT(*) FROM inventory v
        JOIN (SELECT product_id, warehouse,
                     SUM(CASE movement_type WHEN 'inbound' THEN quantity
                                            WHEN 'outbound' THEN -quantity
                                            ELSE quantity END) net
              FROM stock_movements GROUP BY product_id, warehouse) m
          ON m.product_id = v.product_id AND m.warehouse = v.warehouse
        WHERE m.net <> v.on_hand_qty""")
    check("on_hand_qty == net of movements (all 60)", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM inventory v LEFT JOIN stock_movements m "
                "ON m.product_id=v.product_id AND m.warehouse=v.warehouse WHERE m.id IS NULL")
    check("every inventory combo has movements", cur.fetchone()[0] == 0)
    cur.execute("""
        SELECT COUNT(*) FROM (
          SELECT balance_after,
                 SUM(CASE movement_type WHEN 'inbound' THEN quantity
                                        WHEN 'outbound' THEN -quantity
                                        ELSE quantity END)
                 OVER (PARTITION BY product_id, warehouse
                       ORDER BY movement_date, id) run_bal
          FROM stock_movements) t WHERE balance_after <> run_bal""")
    check("balance_after == running balance (every row)", cur.fetchone()[0] == 0)
    cur.execute("SELECT MIN(balance_after) FROM stock_movements")
    check("balance_after never negative", int(cur.fetchone()[0]) >= 0)
    cur.execute("""
        SELECT COUNT(*) FROM inventory v
        JOIN (SELECT product_id, warehouse,
                     SUBSTRING_INDEX(GROUP_CONCAT(balance_after
                       ORDER BY movement_date DESC, id DESC), ',', 1) last_bal
              FROM stock_movements GROUP BY product_id, warehouse) m
          ON m.product_id = v.product_id AND m.warehouse = v.warehouse
        WHERE CAST(m.last_bal AS SIGNED) <> v.on_hand_qty""")
    check("last balance_after == inventory snapshot", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM stock_movements "
                "WHERE movement_type NOT IN ('inbound','outbound','adjustment') "
                "   OR (movement_type IN ('inbound','outbound') AND quantity <= 0) "
                "   OR (movement_type = 'adjustment' AND quantity = 0)")
    check("movement types/quantities valid", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM stock_movements "
                "WHERE (movement_type='adjustment') <> (reference_no IS NULL)")
    check("reference_no iff not adjustment", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(*) FROM stock_movements m JOIN products p ON p.id=m.product_id "
                "WHERE m.movement_date < p.launch_date")
    check("no movements before product launch", cur.fetchone()[0] == 0)
    cur.execute("SELECT COUNT(DISTINCT DATE_FORMAT(movement_date,'%Y-%m')) FROM stock_movements")
    check("movements span >= 20 months", cur.fetchone()[0] >= 20)

    # 9. 只读账号写入被拒
    try:
        cur.execute("INSERT INTO products (sku,name,series,category,unit_price,launch_date) "
                    "VALUES ('X','x','HC','battery_cabinet',1,'2026-01-01')")
        conn.commit()
        check("biz_reader INSERT rejected", False, "insert unexpectedly succeeded")
    except pymysql.err.OperationalError as e:
        check("biz_reader INSERT rejected", e.args[0] == 1142, str(e.args[:2]))

    conn.close()
    if FAILED:
        print(f"\nBIZDB VERIFY: {len(FAILED)} FAILED -> {FAILED}")
        sys.exit(1)
    print("\nBIZDB VERIFY: ALL PASS")


if __name__ == "__main__":
    main()
