"""
recon_dashboard_shell2.py — Recon lanjutan, output RINGKAS (tanpa __domain). READ-ONLY.

Jalankan:
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" < scripts/recon_dashboard_shell2.py
"""
import json
from collections import defaultdict

env  # noqa: F821

DATE_FROM = "2026-08-01"
DATE_TO_EX = "2026-09-01"
ST = ["done", "invoiced", "posted", "paid"]


def sec(t):
    print("\n" + "=" * 60 + f"\n== {t}\n" + "=" * 60)


def rg_compact(model, domain, aggs, groupby, limit=30):
    """read_group tapi output ringkas: hanya groupby + aggregates."""
    rows = env[model].read_group(domain, aggs, groupby)
    out = []
    for r in rows[:limit]:
        d = {}
        for k, v in r.items():
            if k in ("__domain", "__context"):
                continue
            d[k] = v
        out.append(d)
    return out, len(rows)


# ------------------------------------------------------------------
sec("3b. Payment method Agustus (ringkas)")
order_ids = env["pos.order"].search(
    [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST]]).ids
rows, n = rg_compact("pos.payment", [["pos_order_id", "in", order_ids]],
                     ["amount:sum"], ["payment_method_id"], limit=20)
tot = sum(r["amount"] for r in rows)
for r in sorted(rows, key=lambda x: -x["amount"]):
    print(f"  {r['payment_method_id'][1]:22s} n={r['payment_method_id_count']:5d}  Rp {r['amount']:>14,.0f}")
print(f"  TOTAL: Rp {tot:,.0f}  ({n} metode)")

# ------------------------------------------------------------------
sec("3c. Channel — partner_id platform & table_id")
partners = env["res.partner"].search_read([["name", "ilike", "platform"]], ["name"])
print("partner platform:", [p["name"] for p in partners])
by_partner = defaultdict(lambda: [0, 0.0])
for o in env["pos.order"].search_read(
        [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST]],
        ["partner_id", "amount_total", "table_id"]):
    p = o["partner_id"][1] if o["partner_id"] else "(walk-in)"
    by_partner[p][0] += 1
    by_partner[p][1] += o["amount_total"]
for p, (n, amt) in sorted(by_partner.items(), key=lambda x: -x[1][1]):
    print(f"  {p:28s} n={n:5d}  Rp {amt:>14,.0f}")

n_table = env["pos.order"].search_count(
    [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST], ["table_id", "!=", False]])
print(f"order dengan table_id (dine-in): {n_table} / {len(order_ids)}")

# ------------------------------------------------------------------
sec("4b. account.move Agustus per journal (ringkas)")
rows, n = rg_compact("account.move",
                     [["invoice_date", ">=", DATE_FROM], ["invoice_date", "<", DATE_TO_EX], ["state", "=", "posted"]],
                     ["amount_total:sum", "amount_untaxed:sum"], ["journal_id"], limit=20)
for r in rows:
    print(f"  {str(r['journal_id']):40s} n={r['journal_id_count']:5d} total={r['amount_total']:,.0f}")
print(f"  ({n} journal)")

accs = env["account.account"].search_read([], ["code", "name", "account_type"], limit=1000)
tc = defaultdict(int)
for a in accs:
    tc[a["account_type"]] += 1
print("account_type:", dict(tc))

# P&L quick check Agustus: pendapatan vs beban via move lines (posted, tanggal Agustus)
aml = env["account.move.line"].read_group(
    [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX],
     ["account_id.account_type", "in", ["income", "income_other", "expense", "expense_depreciation", "expense_direct_cost", "expense_gnrl_admin"]],
     ["parent_state", "=", "posted"]],
    ["credit:sum", "debit:sum"], ["account_id.account_type"], lazy=False)
for r in aml:
    print(f"  {r['__groupby'] if '__groupby' in r else r.get('account_id.account_type')}: debit={r['debit']:,.0f} credit={r['credit']:,.0f}")

# ------------------------------------------------------------------
sec("5b. Aset (account_asset_management)")
ims = [m for m in env["ir.model"].search([]).mapped("model") if m.startswith("account.asset")]
print("model aset:", ims)
if "account.asset" in ims:
    assets = env["account.asset"].search([])
    print(f"account.asset: {len(assets)}")
    for a in assets[:12]:
        print("  ", a.name, "| state:", a.state,
              "| acquire:", a.acquisition_date if hasattr(a, "acquisition_date") else "-",
              "| value:", getattr(a, "original_value", getattr(a, "value", 0)))
if "account.asset.depreciation.line" in ims:
    n_dl = env["account.asset.depreciation.line"].search_count([])
    print("account.asset.depreciation.line:", n_dl)
    for dl in env["account.asset.depreciation.line"].search([("line_date", ">=", DATE_FROM), ("line_date", "<", DATE_TO_EX)], limit=5):
        print("  DL Agustus:", dl.asset_id.name, dl.amount, dl.line_date, dl.state if hasattr(dl, "state") else "")

# ------------------------------------------------------------------
sec("6b. Stok (ringkas)")
print("gudang:", [(w.name, w.code) for w in env["stock.warehouse"].search([])])
q = env["stock.quant"].read_group([["location_id.usage", "=", "internal"]], ["value:sum", "quantity:sum"], [])
print("nilai persediaan internal:", [(r["value"], r["quantity"]) for r in q])
try:
    v = env["stock.valuation.layer"].read_group(
        [["create_date", ">=", DATE_FROM], ["create_date", "<", DATE_TO_EX]], ["value:sum", "quantity:sum"], [])
    print("SVL Agustus:", [(r["value"], r["quantity"]) for r in v])
except Exception as e:
    print("SVL ERR:", e)
n_scrap = env["stock.scrap"].search_count([["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]])
print("stock.scrap Agustus:", n_scrap)
for s in env["stock.scrap"].search([["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX]], limit=5):
    print("  scrap:", s.product_id.name, s.scrap_qty, s.state)
# waste via stock.move ke scrap/virtual location Agustus
locs = env["stock.location"].search([("scrap_location", "=", True)])
if locs:
    mv = env["stock.move"].read_group(
        [["date", ">=", DATE_FROM], ["date", "<", DATE_TO_EX], ["location_dest_id", "in", locs.ids], ["state", "=", "done"]],
        ["product_qty:sum"], ["product_id"], limit=15)
    print("move ke scrap location Agustus:", len(mv), "produk (sample)")

# ------------------------------------------------------------------
sec("7b. Piutang open")
rec = env["account.move"].search_read(
    [["move_type", "in", ["out_invoice", "out_refund"]], ["state", "=", "posted"],
     ["payment_state", "in", ["not_paid", "partial"]]],
    ["name", "partner_id", "invoice_date_due", "amount_residual"], limit=15, order="invoice_date_due")
print(f"open customer invoice: {len(rec)}")
for r in rec:
    print("  ", r["name"], "|", r["partner_id"][1] if r["partner_id"] else "-", "| due", r["invoice_date_due"], "| Rp", f"{r['amount_residual']:,.0f}")

# ------------------------------------------------------------------
sec("8b. Juli vs Agustus (POS) + harian Agustus")
for label, d1, d2 in [("Juli", "2026-07-01", "2026-08-01"), ("Agustus", DATE_FROM, DATE_TO_EX)]:
    r = env["pos.order"].read_group([["date_order", ">=", d1], ["date_order", "<", d2], ["state", "in", ST]],
                                    ["amount_total:sum"], [])
    print(f"  {label}: Rp {r[0]['amount_total']:,.0f}")
daily = env["pos.order"].read_group(
    [["date_order", ">=", DATE_FROM], ["date_order", "<", DATE_TO_EX], ["state", "in", ST]],
    ["amount_total:sum"], ["date_order:day"], lazy=False)
print(f"  grup harian: {len(daily)} hari")
for d in sorted(daily, key=lambda x: str(x.get("date_order:day") or x["__groupby"]))[:5]:
    print("   ", {k: v for k, v in d.items() if k not in ("__domain", "__context")})

env.cr.rollback()
print("\nRECON-2 SELESAI — read-only.")
