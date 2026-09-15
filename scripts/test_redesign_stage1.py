# -*- coding: utf-8 -*-
"""Test Redesign PowerBI Stage 1 — data sparkline KPI (READ-ONLY).

Jalankan (odoo shell, pola resmi §2 PROGRESS_DASHBOARD.md):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/test_redesign_stage1.py

Memverifikasi field baru payload:
  summary.daily_orders, summary.daily_avg_ticket, finance.daily_net_profit
"""
D = env["geprekyukss.dashboard.data"]

fails = []


def check(name, cond, extra=""):
    if cond:
        print(f"  PASS {name} {extra}")
    else:
        print(f"  FAIL {name} {extra}")
        fails.append(name)


print("=== Skenario 1: Agustus 2026 (semua outlet) ===")
d = D.get_dashboard_data("2026-08-01", "2026-08-31", None)
s, f = d["summary"], d["finance"]

check("summary.daily 31 hari", len(s["daily"]) == 31)
check("summary.daily_orders 31 hari", len(s["daily_orders"]) == 31)
check("summary.daily_avg_ticket 31 hari", len(s["daily_avg_ticket"]) == 31)
check("finance.daily_net_profit 31 hari", len(f["daily_net_profit"]) == 31)

so = sum(x["count"] for x in s["daily_orders"])
check("sum(daily_orders.count) == order_count", so == s["order_count"],
      f"({so} vs {s['order_count']})")

sa = round(sum(x["amount"] for x in s["daily"]), 2)
check("sum(daily.amount) == amount_total", abs(sa - round(s["amount_total"], 2)) < 0.01,
      f"({sa} vs {round(s['amount_total'], 2)})")

# avg ticket harian konsisten: value == amount/count untuk hari ber-order;
# hari tanpa order → count 0 & value 0.0 (frontend skip via x.count)
bad = []
for a, o, t in zip(s["daily"], s["daily_orders"], s["daily_avg_ticket"]):
    if o["count"] > 0 and abs(t["value"] - a["amount"] / o["count"]) > 0.01:
        bad.append(t["date"])
check("daily_avg_ticket konsisten dgn daily & daily_orders", not bad, str(bad[:3]))
zero_bad = [t["date"] for t in s["daily_avg_ticket"]
            if t["count"] == 0 and t["value"] != 0.0]
check("avg_ticket hari tanpa order = value 0 + count 0", not zero_bad)

snp = sum(x["value"] for x in f["daily_net_profit"])
check("sum(daily_net_profit) ≈ net_profit bulan", abs(snp - f["net_profit"]) < 1.0,
      f"({snp:.2f} vs {f['net_profit']:.2f})")

print("=== Skenario 2: Juli 2026 (placeholder, tanpa data) ===")
dj = D.get_dashboard_data("2026-07-01", "2026-07-31", None)
check("Juli has_data False", dj["has_data"] is False)
check("Juli daily_orders 31 hari zeros",
      len(dj["summary"]["daily_orders"]) == 31
      and all(x["count"] == 0 for x in dj["summary"]["daily_orders"]))
check("Juli daily_net_profit 31 hari zeros",
      len(dj["finance"]["daily_net_profit"]) == 31
      and all(x["value"] == 0.0 for x in dj["finance"]["daily_net_profit"]))

print("=== Skenario 3: filter outlet [1] (Pallangga) ===")
d1 = D.get_dashboard_data("2026-08-01", "2026-08-31", [1])
so1 = sum(x["count"] for x in d1["summary"]["daily_orders"])
check("outlet[1]: sum(daily_orders.count) == order_count",
      so1 == d1["summary"]["order_count"], f"({so1} vs {d1['summary']['order_count']})")
sa1 = round(sum(x["amount"] for x in d1["summary"]["daily"]), 2)
check("outlet[1]: sum(daily.amount) == amount_total",
      abs(sa1 - round(d1["summary"]["amount_total"], 2)) < 0.01)

print("=== Stage 3: kategori breakdown beban ===")
exp = f["expenses"]
check("semua expense punya category valid",
      all(e.get("category") in ("hpp", "depreciation", "operational") for e in exp),
      str(sorted({e.get("category") for e in exp})))
hpp_rows = sum(e["amount"] for e in exp if e["category"] == "hpp")
check("sum(category=hpp) == hpp_total", abs(hpp_rows - f["hpp_total"]) < 0.01,
      f"({hpp_rows:.2f} vs {f['hpp_total']:.2f})")
dep_rows = sum(e["amount"] for e in exp if e["category"] == "depreciation")
check("sum(category=depreciation) == depreciation_total",
      abs(dep_rows - f["depreciation_total"]) < 0.01,
      f"({dep_rows:.2f} vs {f['depreciation_total']:.2f})")
# Akun teratas Agustus = HPP Food → harus masuk kategori hpp
top = exp[0] if exp else {}
check("expense teratas (HPP Food) category=hpp", top.get("category") == "hpp",
      f"({top.get('name')})")

print("=== Stage 3: grup metode pembayaran ===")
pay = d["sales"]["payments"]
check("semua payment punya group valid",
      all(p.get("group") in ("qris", "cash", "ewallet", "card", "other") for p in pay),
      str(sorted({p.get("group") for p in pay})))
qris = [p for p in pay if "qris" in p["name"].lower()]
check("payment 'QRIS*' → group=qris", bool(qris) and all(p["group"] == "qris" for p in qris),
      f"({[p['name'] for p in qris]})")
cash = [p for p in pay if "tunai" in p["name"].lower()]
check("payment '*Tunai*' → group=cash", bool(cash) and all(p["group"] == "cash" for p in cash),
      f"({[p['name'] for p in cash]})")
plat = [p for p in pay if "delivery" in p["name"].lower()]
check("payment platform '(Delivery)' → group=other",
      bool(plat) and all(p["group"] == "other" for p in plat),
      f"({[p['name'] for p in plat]})")
# E-wallet (ShopeePay/GO-PAY/OVO) tidak ada di data Agustus berjalan —
# mapping-nya tetap tersedia di gkPaymentColor() bila muncul di bulan lain.
ew = [p for p in pay if any(k in p["name"].lower() for k in ("shopeepay", "go-pay", "gopay", "ovo"))]
check("payment e-wallet → group=ewallet (bila ada)",
      not ew or all(p["group"] == "ewallet" for p in ew),
      f"({[p['name'] for p in ew] or 'tidak ada di data'})")
# Outlet filter ikut mengkategori dengan benar
check("outlet[1]: payments punya group",
      all(p.get("group") for p in d1["sales"]["payments"]))

print()
if fails:
    print(f"GAGAL: {len(fails)} check gagal → {fails}")
else:
    print("ALL PASSED — data sparkline siap untuk frontend")
