"""recon_dashboard_shell6.py — per-bulan via Python, scrap fields, akun beban, aset tetap. READ-ONLY."""
from collections import defaultdict

env  # noqa: F821


def sec(t):
    print("\n" + "=" * 60 + f"\n== {t}\n" + "=" * 60)


def guard(fn):
    try:
        fn()
    except Exception as e:
        print("  ERR:", type(e).__name__, e)


def s_bulan():
    sec("10. POS per bulan 2026")
    orders = env["pos.order"].search_read(
        [["date_order", ">=", "2026-01-01"], ["date_order", "<", "2026-09-01"],
         ["state", "in", ["done", "invoiced", "posted", "paid"]]],
        ["date_order", "amount_total"], limit=200000)
    bulan = defaultdict(lambda: [0, 0.0])
    for o in orders:
        m = str(o["date_order"])[:7]
        bulan[m][0] += 1
        bulan[m][1] += o["amount_total"]
    for m in sorted(bulan):
        n, amt = bulan[m]
        print(f"  {m}  n={n:5d}  Rp {amt:>15,.0f}")


def s_scrap():
    sec("11. stock.scrap")
    f = env["stock.scrap"].fields_get([], attributes=["type"])
    cand = sorted(k for k in f if "date" in k)
    print("fields date:", cand)
    n = env["stock.scrap"].search_count([])
    print("total scrap records:", n)
    if n:
        for s in env["stock.scrap"].search([], limit=5):
            print("  ", s.product_id.name, "| scrap_date:", getattr(s, "scrap_date", None), "| state:", s.state)
    locs = env["stock.location"].search([("scrap_location", "=", True)])
    print("scrap locations:", locs.mapped("display_name"))
    if locs:
        mv = env["stock.move"].search_read(
            [["date", ">=", "2026-08-01"], ["date", "<", "2026-09-01"],
             ["location_dest_id", "in", locs.ids], ["state", "=", "done"]],
            ["product_id", "product_qty", "value"], limit=20)
        print(f"move ke scrap Agustus: {len(mv)}")
        for m in mv[:10]:
            print("   ", m["product_id"][1] if m["product_id"] else "?", m["product_qty"], m.get("value"))


def s_beban():
    sec("12. Akun beban Agustus (top 25)")
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


def s_aset():
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


for fn in (s_bulan, s_scrap, s_beban, s_aset):
    guard(fn)

env.cr.rollback()
print("\nRECON-6 SELESAI — read-only.")
