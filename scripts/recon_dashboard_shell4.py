"""
recon_dashboard_shell4.py — Sisa recon (6d-8d), tiap section di-try/except. READ-ONLY.

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/recon_dashboard_shell4.py
"""
from collections import defaultdict

env  # noqa: F821

DATE_FROM = "2026-08-01"
DATE_TO_EX = "2026-09-01"
ST = ["done", "invoiced", "posted", "paid"]


def sec(t):
    print("\n" + "=" * 60 + f"\n== {t}\n" + "=" * 60)


def guard(fn):
    try:
        fn()
    except Exception as e:
        print("  ERR:", type(e).__name__, e)


# ------------------------------------------------------------------
def s_svl():
    sec("6d-1. stock.valuation.layer")
    print("ada model?", "stock.valuation.layer" in env)
    if "stock.valuation.layer" in env:
        v = env["stock.valuation.layer"].read_group(
            [["create_date", ">=", DATE_FROM], ["create_date", "<", DATE_TO_EX]],
            ["value:sum", "quantity:sum"], [])
        print("SVL Agustus:", [(r["value"], r["quantity"]) for r in v])


def s_scrap():
    sec("6d-2. scrap & waste")
    n = env["stock.scrap"].search_count([["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]])
    print("stock.scrap Agustus:", n)
    for s in env["stock.scrap"].search([["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]], limit=8):
        print("  scrap:", s.product_id.name, s.scrap_qty, s.state)
    locs = env["stock.location"].search([("scrap_location", "=", True)])
    print("scrap locations:", locs.mapped("display_name"))
    if locs:
        mv = env["stock.move"].read_group(
            [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX],
             ["location_dest_id", "in", locs.ids], ["state", "=", "done"]],
            ["product_qty:sum", "value:sum"], ["product_id"], limit=15)
        print(f"move ke scrap Agustus: {len(mv)} grup produk")
        for r in mv[:8]:
            print("   ", r["product_id"][1] if r.get("product_id") else "?", r["product_qty"])


def s_pickings():
    sec("6d-3. picking type Agustus (activity gudang)")
    rows = env["stock.picking"].read_group(
        [["scheduled_date", ">=", DATE_FROM], ["scheduled_date", "<", DATE_TO_EX], ["state", "=", "done"]],
        ["id:count"], ["picking_type_id"], limit=15)
    for r in rows:
        print("  ", r.get("picking_type_id"), r.get("picking_type_id_count"))


def s_piutang():
    sec("7d. Piutang open")
    rec = env["account.move"].search_read(
        [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
         ["payment_state", "in", ["not_paid", "partial"]]],
        ["name", "partner_id", "invoice_date_due", "amount_residual"], limit=15, order="invoice_date_due")
    print(f"open customer invoice: {len(rec)}")
    for r in rec:
        print("  ", r["name"], "|", r["partner_id"][1] if r["partner_id"] else "-",
              "| due", r["invoice_date_due"], "| Rp", f"{r['amount_residual']:,.0f}")
    tot = env["account.move"].read_group(
        [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
         ["payment_state", "in", ["not_paid", "partial"]]],
        ["amount_residual:sum"], [])
    print("total residual:", [(r["amount_residual"]) for r in tot])


def s_bulan():
    sec("8d. Juli vs Agustus + harian")
    for label, d1, d2 in [("Juli", "2026-07-01", "2026-08-01"), ("Agustus", DATE_FROM, DATE_TO_EX)]:
        r = env["pos.order"].read_group(
            [["date_order", ">=", d1], ["date_order", "<", d2], ["state", "in", ST]],
            ["amount_total:sum"], [])
        print(f"  {label}: Rp {r[0]['amount_total']:,.0f}")
    orders = env["pos.order"].search_read(
        [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST]],
        ["date_order", "amount_total"], limit=100000)
    daily = defaultdict(lambda: [0, 0.0])
    for o in orders:
        d = o["date_order"][:10]
        daily[d][0] += 1
        daily[d][1] += o["amount_total"]
    print(f"hari dengan order: {len(daily)}")
    for d in sorted(daily)[:5]:
        print(f"   {d}  n={daily[d][0]:4d}  Rp {daily[d][1]:>13,.0f}")
    print("   ...")
    d_last = sorted(daily)[-1]
    print(f"   {d_last}  n={daily[d_last][0]:4d}  Rp {daily[d_last][1]:>13,.0f}")


def s_kas():
    sec("9d. Posisi kas & bank (saldo akun cash/bank)")
    accs = env["account.account"].search([("account_type", "in", ["asset_cash", "asset_current"])], limit=60)
    for a in accs:
        if a.account_type != "asset_cash":
            continue
        ml = env["account.move.line"].read_group(
            [["account_id", "=", a.id], ["parent_state", "=", "posted"]],
            ["debit:sum", "credit:sum"], [])
        d = ml[0]["debit"] if ml else 0
        c = ml[0]["credit"] if ml else 0
        if d or c:
            print(f"  {a.code:8s} {a.name:35s} saldo = {d - c:>15,.0f}")


for fn in (s_svl, s_scrap, s_pickings, s_piutang, s_bulan, s_kas):
    guard(fn)

env.cr.rollback()
print("\nRECON-4 SELESAI — read-only.")
