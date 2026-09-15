"""
recon_dashboard_shell3.py — Lanjutan recon 3b-8b (fix P&L check). READ-ONLY.

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/recon_dashboard_shell3.py
"""
import json
from collections import defaultdict

env  # noqa: F821

DATE_FROM = "2026-08-01"
DATE_TO_EX = "2026-09-01"
ST = ["done", "invoiced", "posted", "paid"]


def sec(t):
    print("\n" + "=" * 60 + f"\n== {t}\n" + "=" * 60)


# ------------------------------------------------------------------
sec("4c. P&L quick Agustus via account.move.line (groupby account_id)")
PL_TYPES = ["income", "income_other", "expense", "expense_depreciation",
            "expense_direct_cost", "expense_gnrl_admin"]
pl_accounts = env["account.account"].search([("account_type", "in", PL_TYPES)])
print(f"PL accounts: {len(pl_accounts)}")
agg = defaultdict(lambda: {"debit": 0.0, "credit": 0.0})
aml = env["account.move.line"].read_group(
    [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX],
     ["account_id", "in", pl_accounts.ids], ["parent_state", "=", "posted"]],
    ["debit:sum", "credit:sum"], ["account_id"], lazy=False)
by_type = defaultdict(lambda: [0.0, 0.0])
for r in aml:
    acc = env["account.account"].browse(r["account_id"][0])
    by_type[acc.account_type][0] += r["debit"]
    by_type[acc.account_type][1] += r["credit"]
for t, (d, c) in sorted(by_type.items()):
    print(f"  {t:28s} debit={d:>15,.0f}  credit={c:>15,.0f}  net={c-d:>15,.0f}")
inc = by_type.get("income", [0, 0])[1] + by_type.get("income_other", [0, 0])[1]
exp = by_type.get("expense", [0, 0])[0] + by_type.get("expense_depreciation", [0, 0])[0]
print(f"  => income(credit) Agustus: Rp {inc:,.0f}")
print(f"  => expense(debit) Agustus: Rp {exp:,.0f}")

# ------------------------------------------------------------------
sec("5c. Aset (account_asset_management)")
ims = [m for m in env["ir.model"].search([]).mapped("model") if m.startswith("account.asset")]
print("model aset:", ims)
for m in ims:
    try:
        recs = env[m].search([])
        print(f"  {m}: {len(recs)}")
        fields = {f for f in env[m]._fields
                  if any(k in f for k in ("name", "state", "date", "value", "amount", "method"))}
        for r in recs[:10]:
            vals = {f: str(getattr(r, f)) for f in sorted(fields) if not f.startswith("_")}
            print("   ", vals)
    except Exception as e:
        print(f"  {m}: ERR {e}")

# ------------------------------------------------------------------
sec("6c. Stok (ringkas)")
print("gudang:", [(w.name, w.code) for w in env["stock.warehouse"].search([])])
q = env["stock.quant"].read_group([["location_id.usage", "=", "internal"]],
                                  ["value:sum", "quantity:sum"], [])
print("nilai persediaan internal:", [(r["value"], r["quantity"]) for r in q])
try:
    v = env["stock.valuation.layer"].read_group(
        [["create_date", ">=", DATE_FROM], ["create_date", "<", DATE_TO_EX]],
        ["value:sum", "quantity:sum"], [])
    print("SVL Agustus:", [(r["value"], r["quantity"]) for r in v])
except Exception as e:
    print("SVL ERR:", e)
n_scrap = env["stock.scrap"].search_count([["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]])
print("stock.scrap Agustus:", n_scrap)
locs = env["stock.location"].search([("scrap_location", "=", True)])
print("scrap locations:", locs.mapped("display_name"))
if locs:
    mv = env["stock.move"].read_group(
        [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX],
         ["location_dest_id", "in", locs.ids], ["state", "=", "done"]],
        ["product_qty:sum"], ["product_id"], limit=15)
    print(f"move ke scrap Agustus: {len(mv)} grup produk")

# ------------------------------------------------------------------
sec("7c. Piutang open")
rec = env["account.move"].search_read(
    [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
     ["payment_state", "in", ["not_paid", "partial"]]],
    ["name", "partner_id", "invoice_date_due", "amount_residual"], limit=15, order="invoice_date_due")
print(f"open customer invoice: {len(rec)}")
for r in rec:
    print("  ", r["name"], "|", r["partner_id"][1] if r["partner_id"] else "-", "| due", r["invoice_date_due"], "| Rp", f"{r['amount_residual']:,.0f}")

# ------------------------------------------------------------------
sec("8c. Juli vs Agustus + harian")
for label, d1, d2 in [("Juli", "2026-07-01", "2026-08-01"), ("Agustus", DATE_FROM, DATE_TO_EX)]:
    r = env["pos.order"].read_group([["date_order", ">=", d1], ["date_order", "<", d2], ["state", "in", ST]],
                                    ["amount_total:sum"], [])
    print(f"  {label}: Rp {r[0]['amount_total']:,.0f}")
orders_aug = env["pos.order"].search_read(
    [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST]],
    ["date_order", "amount_total"], limit=100000)
daily = defaultdict(lambda: [0, 0.0])
for o in orders_aug:
    d = o["date_order"][:10]
    daily[d][0] += 1
    daily[d][1] += o["amount_total"]
print(f"hari dengan order: {len(daily)}")
for d in sorted(daily)[:6]:
    n, amt = daily[d]
    print(f"   {d}  n={n:4d}  Rp {amt:>13,.0f}")
print("   ...")
d_last = sorted(daily)[-1]
n, amt = daily[d_last]
print(f"   {d_last}  n={n:4d}  Rp {amt:>13,.0f}")

env.cr.rollback()
print("\nRECON-3 SELESAI — read-only.")
