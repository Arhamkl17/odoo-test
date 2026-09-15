"""test_dashboard_data_full.py — uji payload lengkap dashboard. READ-ONLY.

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/test_dashboard_data_full.py
"""
import json

env  # noqa: F821

# reload modul terbaru
env["ir.module.module"].search([("name", "=", "geprekyukss_dashboard")]).button_immediate_upgrade()
env.cr.commit()

Data = env["geprekyukss.dashboard.data"]
aug = Data.get_dashboard_data("2026-08-01", "2026-08-31")
jul = Data.get_dashboard_data("2026-07-01", "2026-07-31")


def brief(d):
    s = d.get("summary", {})
    f = d.get("finance", {})
    sl = d.get("sales", {})
    op = d.get("ops", {})
    return {
        "has_data": d.get("has_data"),
        "summary_total": s.get("amount_total"),
        "orders": s.get("order_count"),
        "vs": s.get("vs"),
        "expense_total": f.get("expense_total"),
        "hpp": f.get("hpp_total"),
        "dep": f.get("depreciation_total"),
        "commission": f.get("platform_commission"),
        "cashflow": f.get("cashflow"),
        "cash_pos_total": round(sum(p["balance"] for p in f.get("cash_positions", [])), 2),
        "balance": f.get("balance"),
        "receivables": f.get("receivables", {}).get("total"),
        "channels": [(c["name"], round(c["amount"])) for c in sl.get("channels", [])],
        "payments_n": len(sl.get("payments", [])),
        "top1": (sl.get("top_by_amount") or [{}])[0].get("name"),
        "assets": {k: round(op.get("assets", {}).get(k, 0) or 0) for k in ("total_gross", "total_accum", "total_net", "total_dep_month")},
        "assets_rows": [(r["name"], round(r["gross"]), round(r["dep_month"]), r["life_years"]) for r in op.get("assets", {}).get("rows", [])],
        "inventory": {k: round(v) if isinstance(v, (int, float)) else v for k, v in op.get("inventory", {}).items() if k != "per_warehouse"},
        "inv_per_wh": [(w["warehouse"], round(w["value"])) for w in op.get("inventory", {}).get("per_warehouse", [])],
        "waste": op.get("waste", {}).get("count"),
    }


print("=== AGUSTUS ===")
print(json.dumps(brief(aug), indent=1, ensure_ascii=False))
print("\n=== JULI (harus placeholder) ===")
print(json.dumps(brief(jul), indent=1, ensure_ascii=False))

env.cr.rollback()
print("\nTEST SELESAI.")
