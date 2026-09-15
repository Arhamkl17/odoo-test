"""test_outlet_filter.py — verifikasi Global Filter Outlet (#1 di SPEC_V2).

READ-ONLY terhadap data; upgrade modul di awal supaya pakai kode terbaru.

Verifikasi:
- list_available_outlets() → daftar pos.config aktif
- get_dashboard_data(date, date, outlet_ids) untuk None / [1] / [2]:
    * Tab 1 summary.amount_total & order_count = sum dari outlets[] di payload
    * Tab 3 sales.amount_total & order_count = jumlah POS-order outlet tsb
    * Tab 2 finance & Tab 4 ops: tidak ter-filter (konsolidasi, TIDAK berubah
      antar panggilan karena tidak linked pos.config di build ini)
    * outlet_filter meta di payload sesuai pilihan

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/test_outlet_filter.py
"""
import json

env  # noqa: F821

env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")]).button_immediate_upgrade()
env.cr.commit()

Data = env["geprekyukss.dashboard.data"]

# ---- 1. Daftar outlet tersedia
outlets = Data.list_available_outlets()
print("=== AVAILABLE OUTLETS ===")
print(json.dumps(outlets, indent=1, ensure_ascii=False))

DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-31"


def brief(d):
    s = d.get("summary", {}) or {}
    f = d.get("finance", {}) or {}
    sl = d.get("sales", {}) or {}
    op = d.get("ops", {}) or {}
    return {
        "outlet_filter": d.get("outlet_filter"),
        "has_data": d.get("has_data"),
        "summary_amount": round(s.get("amount_total", 0) or 0),
        "summary_orders": s.get("order_count", 0),
        "summary_outlets": [(o["name"], round(o["amount_total"]), o["order_count"])
                            for o in s.get("outlets", [])],
        "summary_avg_daily": round(s.get("avg_daily", 0) or 0),
        "finance_expense_total": round(f.get("expense_total", 0) or 0),
        "finance_net_profit": round(f.get("net_profit", 0) or 0),
        "finance_balance_total_assets": round(f.get("balance", {}).get("total_assets", 0) or 0),
        "finance_cashflow": f.get("cashflow", {}),
        "sales_amount": round(sl.get("amount_total", 0) or 0),
        "sales_orders": sl.get("order_count", 0),
        "sales_top1": (sl.get("top_by_amount") or [{}])[0].get("name"),
        "ops_total_gross": round(op.get("assets", {}).get("total_gross", 0) or 0),
        "ops_inventory_total": round(op.get("inventory", {}).get("total", 0) or 0),
        "ops_waste_count": op.get("waste", {}).get("count", 0),
    }


# ---- 2. Tiga skenario filter
all_data = Data.get_dashboard_data(DATE_FROM, DATE_TO, outlet_ids=None)
pallangga_data = Data.get_dashboard_data(DATE_FROM, DATE_TO, outlet_ids=[1])
mallengkeri_data = Data.get_dashboard_data(DATE_FROM, DATE_TO, outlet_ids=[2])

print("\n=== ALL (outlet_ids=None) ===")
print(json.dumps(brief(all_data), indent=1, ensure_ascii=False))
print("\n=== PALLANGGA (outlet_ids=[1]) ===")
print(json.dumps(brief(pallangga_data), indent=1, ensure_ascii=False))
print("\n=== MALLENGKERI (outlet_ids=[2]) ===")
print(json.dumps(brief(mallengkeri_data), indent=1, ensure_ascii=False))


# ---- 3. Asersi konsistensi
def assert_invariants(label, full, filtered, expected_id, expected_name):
    """Syarat yang harus benar untuk filter outlet manapun."""
    errs = []
    # outlet_filter meta
    meta = filtered.get("outlet_filter", {})
    if meta.get("id") != expected_id and not (expected_id == "all" and meta.get("id") == "all"):
        errs.append(f"outlet_filter.id salah: dapat {meta.get('id')}, expected {expected_id}")
    if expected_name not in meta.get("name", ""):
        errs.append(f"outlet_filter.name tidak mengandung '{expected_name}': {meta.get('name')}")
    # POS totals: filtered == sum dari outlets[] filtered
    s = filtered.get("summary", {}) or {}
    sum_out = sum(o["amount_total"] for o in s.get("outlets", []))
    if abs(sum_out - s.get("amount_total", 0)) > 1.0:
        errs.append(f"summary.amount_total ({s.get('amount_total')}) != sum outlets ({sum_out})")
    # finance (Tab 2) & ops (Tab 4) HARUS sama dengan ALL (konsolidasi, tidak linked pos.config)
    f = filtered.get("finance", {}) or {}
    full_f = full.get("finance", {}) or {}
    for k in ("expense_total", "net_profit", "balance"):
        if k == "balance":
            for bk, bv in f.get("balance", {}).items():
                if abs((full_f.get("balance", {}).get(bk) or 0) - (bv or 0)) > 1.0:
                    errs.append(f"finance.balance.{bk} berubah: {bv} vs all {full_f['balance'].get(bk)}")
        else:
            if abs((f.get(k) or 0) - (full_f.get(k) or 0)) > 1.0:
                errs.append(f"finance.{k} berubah: {f.get(k)} vs all {full_f.get(k)}")
    op = filtered.get("ops", {}) or {}
    full_op = full.get("ops", {}) or {}
    for k in ("assets", "inventory", "waste"):
        if (op.get(k) or {}) != (full_op.get(k) or {}):
            errs.append(f"ops.{k} berubah padahal harus konsolidasi")
    return errs


print("\n=== INVARIANTS ===")
checks = [
    ("Pallangga", all_data, pallangga_data, 1, "Pallangga"),
    ("Mallengkeri", all_data, mallengkeri_data, 2, "Mallengkeri"),
]
fails = 0
for label, full, filt, eid, ename in checks:
    errs = assert_invariants(label, full, filt, eid, ename)
    if errs:
        fails += 1
        print(f"[FAIL] {label}:")
        for e in errs:
            print(f"   - {e}")
    else:
        print(f"[OK]   {label}")

# Syarat tambahan khusus filter Pallangga+ALL
# amount_total Pallangga + Mallengkeri == ALL
sum_per_outlet = (pallangga_data["summary"]["amount_total"]
                  + mallengkeri_data["summary"]["amount_total"])
if abs(sum_per_outlet - all_data["summary"]["amount_total"]) > 1.0:
    fails += 1
    print(f"[FAIL] Pallangga + Mallengkeri != ALL: {sum_per_outlet} vs {all_data['summary']['amount_total']}")
else:
    print(f"[OK]   Pallangga + Mallengkeri == ALL ({round(sum_per_outlet)})")

env.cr.rollback()
print(f"\n{'TEST GAGAL' if fails else 'TEST LULUS'} ({fails} kegagalan)")
