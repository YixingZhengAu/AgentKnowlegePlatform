"""生成 demo_biz 的种子数据 → init/03-seed.sql。

纯 stdlib、固定随机种子,任何机器上重跑产出逐字节一致。
数据设计要点(对应 S3-PLAN A1 的自测项):
  * 近 24 个月(2024-09 ~ 2026-08)每月都有订单,澳洲光伏旺季(10 月–次年 3 月)加权,
    第二年整体上浮 15%,给"趋势/同比"类问题留出可看的形状
  * orders.total_amount 严格等于订单行聚合(生成时就按行算头)
  * 州分布 NSW > VIC > QLD > SA > WA;经销商拿更低折扣
  * 约 7% 订单 cancelled;订单状态与下单时间的新旧一致
  * 库存 = 出入库流水的净额:inventory.on_hand_qty 严格等于 stock_movements 汇总,
    且滚动余额任意时点不为负;产品上市(launch_date)前无流水
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

rng = random.Random(42)
TODAY = date(2026, 8, 23)  # 固定锚点,保证确定性
OUT = Path(__file__).parent / "init" / "03-seed.sql"

STATES = ["NSW", "VIC", "QLD", "SA", "WA"]
STATE_WEIGHTS = [0.32, 0.26, 0.20, 0.12, 0.10]

# ---------- products(20)----------
PRODUCTS: list[tuple[str, str, str, str, float, str]] = [
    # (sku, name, series, category, list_price_aud, launch_date)
    ("HC-50",   "PowerCab HC-50 Battery Cabinet 50kWh",    "HC",  "battery_cabinet", 42000,  "2023-02-01"),
    ("HC-100",  "PowerCab HC-100 Battery Cabinet 100kWh",  "HC",  "battery_cabinet", 76000,  "2023-02-01"),
    ("HC-215",  "PowerCab HC-215 Battery Cabinet 215kWh",  "HC",  "battery_cabinet", 148000, "2023-09-15"),
    ("HC-300",  "PowerCab HC-300 Battery Cabinet 300kWh",  "HC",  "battery_cabinet", 195000, "2024-03-01"),
    ("HC-500",  "PowerCab HC-500 Battery Cabinet 500kWh",  "HC",  "battery_cabinet", 310000, "2024-08-01"),
    ("HC-1000", "PowerCab HC-1000 Battery Cabinet 1MWh",   "HC",  "battery_cabinet", 585000, "2025-05-01"),
    ("INV-10K",  "SolarWave INV-10K String Inverter 10kW",   "INV", "inverter", 3200,  "2022-06-01"),
    ("INV-25K",  "SolarWave INV-25K String Inverter 25kW",   "INV", "inverter", 6800,  "2022-06-01"),
    ("INV-50K",  "SolarWave INV-50K String Inverter 50kW",   "INV", "inverter", 11500, "2023-01-10"),
    ("INV-110K", "SolarWave INV-110K String Inverter 110kW", "INV", "inverter", 21000, "2023-11-01"),
    ("INV-250K", "SolarWave INV-250K Central Inverter 250kW","INV", "inverter", 39000, "2024-06-01"),
    ("INV-333K", "SolarWave INV-333K Central Inverter 333kW","INV", "inverter", 47500, "2025-02-01"),
    ("EMS-LITE", "GridMind EMS Lite Licence",        "EMS", "ems_software", 5500,  "2023-05-01"),
    ("EMS-PRO",  "GridMind EMS Pro Licence",         "EMS", "ems_software", 18000, "2023-05-01"),
    ("EMS-ENT",  "GridMind EMS Enterprise Licence",  "EMS", "ems_software", 56000, "2024-04-01"),
    ("ACC-RACK",  "HC Series Mounting Rack Kit",          "ACC", "accessory", 1450, "2023-02-01"),
    ("ACC-CBL50", "DC Cable Kit 50m",                     "ACC", "accessory", 380,  "2022-06-01"),
    ("ACC-GATE",  "Monitoring Gateway G2",                "ACC", "accessory", 920,  "2023-08-01"),
    ("ACC-METER", "Smart Energy Meter 3-Phase",           "ACC", "accessory", 640,  "2022-06-01"),
    ("ACC-COOL",  "HC Series HVAC Cooling Module",        "ACC", "accessory", 5200, "2023-09-15"),
]
QTY_RANGE = {"HC": (1, 4), "INV": (1, 12), "EMS": (1, 2), "ACC": (2, 30)}
SERIES_PICK_WEIGHTS = {"HC": 0.30, "INV": 0.35, "EMS": 0.15, "ACC": 0.20}

# ---------- customers(80)----------
NAME_A = ["Harbour", "Southern", "Pacific", "Summit", "Ironbark", "Coastal", "Redgum", "Boomerang",
          "Kestrel", "Wattle", "Granite", "Horizon", "Sunline", "Bluegum", "Meridian", "Opal",
          "Sandstone", "Crestway", "Northbank", "Silvergrove"]
NAME_B = ["Manufacturing", "Cold Storage", "Logistics", "Fabrication", "Food Processing", "Packaging",
          "Industrial Park", "Business Park", "Shopping Centre", "Distribution", "Engineering",
          "Recycling", "Dairy Co-op", "Aggregates", "Textiles", "Beverages"]
INDUSTRIES = ["factory", "industrial_park", "commercial_complex", "logistics", "agriculture"]
CHANNELS = ["direct", "distributor"]

# ---------- sales reps(15;州内配额 4/4/3/2/2)----------
REP_NAMES = ["Olivia Chen", "Jack Thompson", "Mia Nguyen", "Noah Williams", "Ava Patel",
             "Liam O'Connor", "Isla Martin", "Ethan Zhang", "Grace Taylor", "Lucas Brown",
             "Zoe Anderson", "Harper Singh", "Oscar White", "Ruby Johnson", "Leo Costa"]
REP_STATES = ["NSW"] * 4 + ["VIC"] * 4 + ["QLD"] * 3 + ["SA"] * 2 + ["WA"] * 2

WAREHOUSES = ["Sydney", "Melbourne", "Brisbane"]

# 月份权重:澳洲光伏旺季 10–3 月
MONTH_W = {1: 1.2, 2: 1.0, 3: 1.1, 4: 0.8, 5: 0.7, 6: 0.7, 7: 0.8, 8: 0.9, 9: 1.0, 10: 1.2, 11: 1.3, 12: 1.3}


def months() -> list[tuple[int, int]]:
    out, y, m = [], 2024, 9
    while (y, m) <= (2026, 8):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def esc(s: str) -> str:
    return s.replace("'", "''")


def main() -> None:
    lines: list[str] = ["USE demo_biz;", "SET NAMES utf8mb4;"]

    def emit(table: str, cols: list[str], rows: list[str], chunk: int = 200) -> None:
        for i in range(0, len(rows), chunk):
            lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES")
            lines.append(",\n".join(rows[i : i + chunk]) + ";")

    # products
    emit("products", ["sku", "name", "series", "category", "unit_price", "launch_date", "is_active"],
         [f"('{p[0]}', '{esc(p[1])}', '{p[2]}', '{p[3]}', {p[4]:.2f}, '{p[5]}', 1)" for p in PRODUCTS])

    # customers
    cust_rows, cust_states, cust_channels, used = [], [], [], set()
    while len(cust_rows) < 80:
        nm = f"{rng.choice(NAME_A)} {rng.choice(NAME_B)} Pty Ltd"
        if nm in used:
            continue
        used.add(nm)
        st = rng.choices(STATES, STATE_WEIGHTS)[0]
        ch = rng.choices(CHANNELS, [0.55, 0.45])[0]
        ind = rng.choice(INDUSTRIES)
        created = date(2023, 1, 1) + timedelta(days=rng.randint(0, 900))
        cust_states.append(st)
        cust_channels.append(ch)
        cust_rows.append(f"('{esc(nm)}', '{st}', '{ch}', '{ind}', '{created}')")
    emit("customers", ["name", "state", "channel_type", "industry", "created_at"], cust_rows)

    # sales_reps
    rep_rows = []
    for name, st in zip(REP_NAMES, REP_STATES):
        hired = date(2021, 1, 1) + timedelta(days=rng.randint(0, 1400))
        rep_rows.append(f"('{esc(name)}', '{st}', '{rng.choices(['direct','channel'],[0.6,0.4])[0]}', '{hired}', 1)")
    emit("sales_reps", ["name", "state", "team", "hired_date", "is_active"], rep_rows)
    reps_by_state: dict[str, list[int]] = {}
    for i, st in enumerate(REP_STATES, start=1):
        reps_by_state.setdefault(st, []).append(i)

    # orders + order_items
    order_rows, item_rows = [], []
    seq = 0
    for y, m in months():
        growth = 1.15 if y == 2026 or (y == 2025 and m >= 9) else 1.0
        n = round(50 * MONTH_W[m] * growth)
        month_end = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
        last_day = 23 if (y, m) == (2026, 8) else month_end
        for _ in range(n):
            seq += 1
            cid = rng.randint(1, 80)
            st = cust_states[cid - 1]
            rep = rng.choice(reps_by_state[st]) if rng.random() < 0.9 else rng.randint(1, 15)
            od = date(y, m, rng.randint(1, last_day))
            age = (TODAY - od).days
            r = rng.random()
            if r < 0.07:
                status = "cancelled"
            elif age > 90:
                status = "completed" if rng.random() < 0.9 else "shipped"
            elif age > 30:
                status = rng.choices(["completed", "shipped", "paid"], [0.4, 0.4, 0.2])[0]
            else:
                status = rng.choices(["pending", "paid", "shipped"], [0.3, 0.4, 0.3])[0]
            # 行:1–4 个不同产品
            n_items = rng.choices([1, 2, 3, 4], [0.35, 0.35, 0.2, 0.1])[0]
            chosen = []
            while len(chosen) < n_items:
                series = rng.choices(list(SERIES_PICK_WEIGHTS), list(SERIES_PICK_WEIGHTS.values()))[0]
                cands = [i for i, p in enumerate(PRODUCTS) if p[2] == series and i not in chosen
                         and date.fromisoformat(p[5]) <= od]
                if cands:
                    chosen.append(rng.choice(cands))
                elif all(date.fromisoformat(p[5]) > od for p in PRODUCTS):
                    break
            total = Decimal("0")
            disc_lo, disc_hi = (0.82, 0.92) if cust_channels[cid - 1] == "distributor" else (0.90, 1.00)
            for pi in chosen:
                p = PRODUCTS[pi]
                lo, hi = QTY_RANGE[p[2]]
                qty = rng.randint(lo, hi)
                price = Decimal(f"{p[4] * rng.uniform(disc_lo, disc_hi):.2f}")
                amt = price * qty
                total += amt
                item_rows.append(f"({seq}, {pi + 1}, {qty}, {price}, {amt})")
            order_no = f"SO-{y}-{seq:05d}"
            order_rows.append(f"('{order_no}', {cid}, {rep}, '{od}', '{status}', {total})")
    emit("orders", ["order_no", "customer_id", "sales_rep_id", "order_date", "status", "total_amount"], order_rows)
    emit("order_items", ["order_id", "product_id", "quantity", "unit_price", "line_amount"], item_rows)

    # stock_movements + inventory:逐月模拟出入库,快照 on_hand_qty = 流水净额(强不变量,
    # 与"订单头总额 = 行聚合"同款设计)。月内事件按 入库(1-8 日)→ 出库(9-26 日)→
    # 盘点调整(27-28 日)排日,保证任意时点的滚动余额不为负。
    batch_range = {"HC": (4, 30), "INV": (20, 150), "EMS": (8, 60), "ACC": (80, 900)}
    mv_rows, inv_rows = [], []
    doc_seq: dict[tuple[str, int], int] = {}

    def ref_no(prefix: str, y: int) -> str:
        doc_seq[(prefix, y)] = doc_seq.get((prefix, y), 0) + 1
        return f"{prefix}-{y}-{doc_seq[(prefix, y)]:05d}"

    for pi, p in enumerate(PRODUCTS, start=1):
        launch = date.fromisoformat(p[5])
        lo, hi = batch_range[p[2]]
        for wh in WAREHOUSES:
            balance, last_dt = 0, None
            for y, m in months():
                if (y, m) < (launch.year, launch.month):
                    continue
                cap = 23 if (y, m) == (2026, 8) else 28  # 锚点月不产生"未来"流水

                def day(a: int, b: int) -> date:
                    return date(y, m, rng.randint(min(a, cap), min(b, cap)))

                if rng.random() < 0.30 or balance < lo:
                    q, d = rng.randint(lo, hi), day(1, 8)
                    balance += q
                    mv_rows.append(f"({pi}, '{wh}', 'inbound', {q}, {balance}, '{d}', '{ref_no('GRN', y)}')")
                    last_dt = d
                if balance > 0 and rng.random() < 0.55:
                    q, d = rng.randint(1, max(1, balance * 2 // 3)), day(9, 26)
                    balance -= q
                    mv_rows.append(f"({pi}, '{wh}', 'outbound', {q}, {balance}, '{d}', '{ref_no('DO', y)}')")
                    last_dt = d
                if rng.random() < 0.05:
                    q = rng.choice([x for x in range(-3, 4) if x != 0 and balance + x >= 0])
                    d = day(27, 28)
                    balance += q
                    mv_rows.append(f"({pi}, '{wh}', 'adjustment', {q}, {balance}, '{d}', NULL)")
                    last_dt = d
            reserved = rng.randint(0, balance // 4) if balance else 0
            ts = datetime(last_dt.year, last_dt.month, last_dt.day, rng.randint(8, 18), rng.randint(0, 59))
            inv_rows.append(f"({pi}, '{wh}', {balance}, {reserved}, '{ts:%Y-%m-%d %H:%M:%S}')")
    emit("inventory", ["product_id", "warehouse", "on_hand_qty", "reserved_qty", "updated_at"], inv_rows)
    emit("stock_movements",
         ["product_id", "warehouse", "movement_type", "quantity", "balance_after", "movement_date", "reference_no"], mv_rows)

    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({len(order_rows)} orders, {len(item_rows)} items, {len(mv_rows)} movements)")


if __name__ == "__main__":
    main()
