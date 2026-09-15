"""recon_dashboard_shell5.py — cek per-bulan, scrap fields, akun beban. READ-ONLY."""
from collections import defaultdict

env  # noqa: F821


def sec(t):
    print("\n" + "=" * 60 + f"\n== {t}\n" + "=" * 60)


sec("10. POS per bulan 2026")
rows = env["pos.order"].read_group(
    [["date_order", ">=", "2026-01-01"], ["date_order", "<", "2026-09-01"],
     ["state", "in", ["done", "invoiced", "posted", "paid"]]],
    ["amount_total:sum"], ["date_order:month"], lazy=False)
for r in sorted(rows, key=lambda x: str(x.get("date_order:month") or x["__groupby"])):
    g = r.get("date_order:month") or r["__groupby"]
    print(f"  {g}  n={r['date_order_count']:5d}  Rp {r['amount_total']:>15,.0f}")

sec("11. stock.scrap fields")
f = env["stock.scrap"].fields_get([], attributes=["type"])
cand = [k for k in f if "date" in k or k in ("state",)]
print("fields date/state:", cand[:10])
n = env["stock.scrap"].search_count([])
print("total scrap records:", n)
if n:
    s0 = env["stock.scrap"].search([], limit=3)
    for s in s0:
        print("  ", s.product_id.name, getattr(s, "scrap_date", None), s.state)

sec("12. Akun beban (untuk breakdown Tab 2)")
exp = env["account.account"].search([("account_type", "in", ["expense", "expense_direct_cost"])])
ml = env["account.move.line"].read_group(
    [["date", ">=", "2026-08-01"], ["date", "<", "2026-09-01"],
     ["account_id", "in", exp.ids], ["parent_state", "=", "posted"]],
    ["debit:sum"], ["account_id"], lazy=False)
lines = []
for r in ml:
    a = env["account.account"].browse(r["account_id"][0])
    if r["debit"] > 0:
        lines.append((r["debit"], a.code, a.name))
for d, c, nm in sorted(lines, reverse=True)[:25]:
    print(f"  {c:10s} {nm:45s} Rp {d:>14,.0f}")

sec("13. Aset tetap — saldo akun asset_fixed")
fa = env["account.account"].search([("account_type", "=", "asset_fixed")])
for a in fa:
    ml = env["account.move.line"].read_group(
        [["account_id", "=", a.id], ["parent_state", "=", "posted"]],
        ["debit:sum", "credit:sum"], [])
    d = ml[0]["debit"] if ml else 0
    c = ml[0]["credit"] if ml else 0
    if d or c:
        print(f"  {a.code:10s} {a.name:45s} saldo = {d - c:>15,.0f}")

env.cr.rollback()
print("\nRECON-5 SELESAI — read-only.")
