# -*- coding: utf-8 -*-
"""
RECON READ-ONLY — baseline Agustus 2026 untuk rencana Juni/Juli.
Lihat JUNI_JULI_DATA-spec.md §1 & §5.1 (tahap 1).

Tujuan:
  A. Environment & kondisi fiscal year / asset register
  B. POS Agustus: sesi, order, omzet per outlet & channel, harian, avg ticket
  C. Metode pembayaran POS Agustus
  D. Akuntansi Agustus: pendapatan, beban, laba, aset tetap, akumulasi, penyusutan
  E. Saldo kas/bank per 31 Agu
  F. Persediaan: quant per gudang, stock move, pembelian
  G. Partner (platform / pelanggan / supplier)
  H. Produk & BOM
  I. Jurnal
  J. AR/AP terbuka per 31 Agu
  K. Modal disetor
  L. Cek aktivitas Juni & Juli 2026 (harus kosong)
  M. Konfigurasi pajak (informational — TIDAK diubah, spec D22)
  N. Invariant: TB debit vs kredit

Jalankan (odoo shell, read-only):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo" < scripts/juni_juli_01_recon.py

TIDAK menulis apa pun: tutup dengan env.cr.rollback().
"""
from collections import defaultdict

SEP = "=" * 78
AUG1, AUG2 = "2026-08-01", "2026-08-31"
AUG2X = "2026-09-01"

def sec(t):
    print("\n" + SEP + "\n" + t + "\n" + SEP)

def rp(v):
    return "%16.2f" % (v or 0.0)

def norm(v):
    return v or 0.0


# ===========================================================================
sec("A. ENVIRONMENT / FISCAL YEAR / ASSET REGISTER")
# ===========================================================================
company = env.company
print("company     :", company.id, company.name, "| currency:", company.currency_id.name)
print("odoo        :", env["ir.config_parameter"].sudo().get_param("database.create_date") or "-")

for model in ("date.range", "date.range.type", "account.fiscal.year", "account.asset"):
    try:
        print("%-22s records = %d" % (model, env[model].search_count([])))
    except Exception as e:
        print("%-22s ERROR %s" % (model, repr(e)[:90]))

mods = env["ir.module.module"].search([("name", "in", [
    "account_asset_management", "account_account_tag_code", "mis_builder",
    "account_financial_report", "account_journal_restrict_mode", "geprekyukss_dashboard"])])
for m in mods:
    print("module %-32s %s" % (m.name, m.state))

for fld in ("fiscalyear_lock_date", "sale_lock_date", "purchase_lock_date", "hard_lock_date"):
    print("%-22s %s" % (fld + ":", company[fld] if fld in company._fields else "(field tidak ada)"))


# ===========================================================================
sec("B. POS AGUSTUS — SESI, ORDER, OMZET")
# ===========================================================================
POS = env["pos.order"]
Sess = env["pos.session"]

configs = env["pos.config"].search([])
print("pos.config:")
for c in configs:
    print("   [%d] %s" % (c.id, c.name))

sessions = Sess.search([("start_at", ">=", AUG1), ("start_at", "<", AUG2X)])
print("\nsesi Agustus: %d" % len(sessions))
print("   by state:", dict(defaultdict(int, {s.state: sum(1 for x in sessions if x.state == s.state) for s in sessions})))
hours = defaultdict(int)
for s in sessions:
    if s.start_at:
        hours[s.start_at.hour] += 1
print("   jam buka  :", dict(sorted(hours.items())))
if sessions:
    first, last = min(sessions.mapped("start_at")), max(sessions.mapped("start_at"))
    print("   rentang   :", first, "->", last)

states = defaultdict(int)
for o in POS.search([("date_order", ">=", AUG1), ("date_order", "<", AUG2X)]):
    states[o.state] += 1
print("\norder Agustus per state:", dict(states))

dom_ok = [("date_order", ">=", AUG1), ("date_order", "<", AUG2X),
          ("state", "in", ["done", "invoiced", "paid"])]
orders = POS.search(dom_ok)
total = sum(norm(o.amount_total) for o in orders)
n = len(orders)
print("\nomzet POS Agustus : Rp %s  (%d order)" % (rp(total).strip(), n))
print("avg ticket        : Rp %s" % (rp(total / n if n else 0).strip(),))

by_outlet = defaultdict(lambda: [0.0, 0])
by_channel = defaultdict(lambda: [0.0, 0])
for o in orders:
    cfg = o.config_id.name or "-"
    by_outlet[cfg][0] += norm(o.amount_total)
    by_outlet[cfg][1] += 1
    ch = o.partner_id.name if o.partner_id else "Walk-in"
    by_channel[ch][0] += norm(o.amount_total)
    by_channel[ch][1] += 1

print("\nper outlet:")
for k, (amt, cnt) in sorted(by_outlet.items(), key=lambda x: -x[1][0]):
    print("   %-30s Rp %s  %5d order  (%.2f%%)" % (k, rp(amt).strip(), cnt, 100.0 * amt / total if total else 0))

print("\nper channel (via partner):")
for k, (amt, cnt) in sorted(by_channel.items(), key=lambda x: -x[1][0]):
    print("   %-30s Rp %s  %5d order  (%.2f%%)" % (k, rp(amt).strip(), cnt, 100.0 * amt / total if total else 0))

daily = defaultdict(float)
daily_n = defaultdict(int)
for o in orders:
    d = str(o.date_order)[:10]
    daily[d] += norm(o.amount_total)
    daily_n[d] += 1
print("\nharian Agustus: %d hari, min Rp %s / max Rp %s" % (
    len(daily), rp(min(daily.values())).strip(), rp(max(daily.values())).strip()))
print("   hari pertama:", sorted(daily)[0], " hari terakhir:", sorted(daily)[-1])

print("\nomzet POS per bulan 2026 (cek bulan lain kosong):")
for month, amt, cnt in POS._read_group(
        [("state", "in", ["done", "invoiced", "paid"]), ("date_order", ">=", "2026-01-01")],
        ["date_order:month"], ["amount_total:sum", "id:count"]):
    print("   %-10s Rp %s  %5d order" % (month, rp(amt).strip(), cnt))


# ===========================================================================
sec("C. METODE PEMBAYARAN POS AGUSTUS")
# ===========================================================================
Pay = env["pos.payment"]
rows = Pay._read_group(
    [("payment_date", ">=", AUG1), ("payment_date", "<", AUG2X),
     ("session_id.state", "in", ["closed", "closing_control"])],
    ["payment_method_id"], ["amount:sum", "id:count"])
pay_total = 0.0
for pm, amt, cnt in sorted(rows, key=lambda x: -(x[1] or 0)):
    amt = norm(amt)
    pay_total += amt
    print("   %-32s Rp %s  %5d" % (pm.name if pm else "-", rp(amt).strip(), cnt))
print("   TOTAL pembayaran: Rp %s" % rp(pay_total).strip())


# ===========================================================================
sec("D. AKUNTANSI AGUSTUS — PENDAPATAN / BEBAN / LABA / ASET TETAP")
# ===========================================================================
AML = env["account.move.line"]
dom_post = [("parent_state", "=", "posted"), ("date", ">=", AUG1), ("date", "<", AUG2X)]

INC_TYPES = ["income", "income_other"]
EXP_TYPES = ["expense", "expense_direct_cost", "expense_depreciation"]

def agg(dom):
    """Sum satu aggregate balance (aman bila tanpa baris)."""
    rows = AML._read_group(dom, [], ["balance:sum"])
    return sum(norm(x) for x in rows[0]) if rows else 0.0

inc_detail = AML._read_group(
    dom_post + [("account_id.account_type", "in", INC_TYPES)],
    ["account_id"], ["balance:sum"])
exp_detail = AML._read_group(
    dom_post + [("account_id.account_type", "in", EXP_TYPES)],
    ["account_id"], ["balance:sum"])

# balance = debit - credit. Akun pendapatan bersaldo kredit (negatif),
# akun beban bersaldo debit (positif) -> normalisasi ke angka laporan.
income = -sum(norm(b) for _a, b in inc_detail)
expense = sum(norm(b) for _a, b in exp_detail)

print("pendapatan posted Agustus : Rp %s" % rp(income).strip())
print("beban posted Agustus      : Rp %s" % rp(expense).strip())
print("LABA BERSIH (TB-based)    : Rp %s" % rp(income - expense).strip())

print("\nrincian pendapatan:")
for acc, bal in sorted(inc_detail, key=lambda x: x[1]):
    print("   %-12s %-46s Rp %s" % (acc.code, acc.name[:46], rp(-bal).strip()))

print("\nrincian beban:")
for acc, bal in sorted(exp_detail, key=lambda x: -x[1]):
    print("   %-12s %-46s Rp %s" % (acc.code, acc.name[:46], rp(-bal).strip()))

Acc = env["account.account"].with_context(active_test=False)
assets = Acc.search([("account_type", "=", "asset_fixed")])
print("\naset tetap (asset_fixed) — dipisah gross vs akumulasi:")
gross = akum = 0.0
for a in assets:
    bal = agg([("account_id", "=", a.id), ("parent_state", "=", "posted"), ("date", "<=", AUG2)])
    if "akumulasi" in (a.name or "").lower():
        akum += bal
    elif abs(bal) >= 0.005:
        gross += bal
    print("   %-12s %-44s Rp %s  active=%s" % (a.code, a.name[:44], rp(bal).strip(), a.active))
print("   GROSS aset (tanpa akumulasi): Rp %s" % rp(gross).strip())
print("   TOTAL akumulasi penyusutan  : Rp %s" % rp(akum).strip())
print("   NILAI BUKU                  : Rp %s" % rp(gross + akum).strip())

print("\nakumulasi penyusutan (nama mengandung 'penyusutan', tipe aset/liability):")
akum = 0.0
for a in Acc.search([("name", "ilike", "akumulasi")]):
    bal = sum(norm(x) for x in AML._read_group(
        [("account_id", "=", a.id), ("parent_state", "=", "posted"), ("date", "<=", AUG2)], [], ["balance:sum"])[0])
    akum += bal
    print("   %-12s %-44s Rp %s  (%s)" % (a.code, a.name[:44], rp(bal).strip(), a.account_type))
print("   TOTAL akumulasi: Rp %s" % rp(akum).strip())

print("\nbeban penyusutan Agustus (nama mengandung 'penyusutan'):")
for a in Acc.search([("name", "ilike", "penyusutan")]):
    grp = AML._read_group(dom_post + [("account_id", "=", a.id)], [], ["balance:sum"])
    bal = sum(norm(x) for x in grp[0])
    if abs(bal) >= 0.005:
        print("   %-12s %-44s Rp %s" % (a.code, a.name[:44], rp(-bal).strip()))


# ===========================================================================
sec("E. SALDO KAS & BANK PER 31 AGUSTUS")
# ===========================================================================
cash = Acc.search([("account_type", "=", "asset_cash")])
tot_cash = 0.0
print("%-12s %-40s %16s  %s" % ("CODE", "NAME", "SALDO 31 AGU", "ACTIVE"))
for a in cash:
    bal = sum(norm(x) for x in AML._read_group(
        [("account_id", "=", a.id), ("parent_state", "=", "posted"), ("date", "<=", AUG2)], [], ["balance:sum"])[0])
    tot_cash += bal
    flag = "" if a.active else "  (nonaktif)"
    if abs(bal) >= 0.005 or a.active:
        print("%-12s %-40s %s%s" % (a.code, a.name[:40], rp(bal), flag))
print("TOTAL kas & bank 31 Agu: Rp %s" % rp(tot_cash).strip())


# ===========================================================================
sec("F. PERSEDIAAN — QUANT, MOVE, PEMBELIAN AGUSTUS")
# ===========================================================================
Quant = env["stock.quant"]
qdom = [("location_id.usage", "=", "internal")]
has_value = "value" in Quant._fields
try:
    rows = Quant._read_group(qdom, ["location_id"], (["value:sum"] if has_value else ["quantity:sum"]))
    print("stock.quant per lokasi internal (%s):" % ("value" if has_value else "quantity"))
    qtotal = 0.0
    for loc, val in rows:
        qtotal += norm(val)
        print("   %-40s %s" % ((loc.display_name or "-")[:40], rp(val)))
    print("   TOTAL: %s" % rp(qtotal).strip())
except Exception as e:
    print("quant read error:", repr(e)[:200])

print("\nstock.move Agustus (state done):")
try:
    SM = env["stock.move"]
    grp = SM._read_group(
        [("state", "=", "done"), ("date", ">=", AUG1), ("date", "<", AUG2X)],
        ["location_id.usage", "location_dest_id.usage"], ["value:sum", "id:count"])
    for src, dst, val, cnt in grp:
        print("   %-10s -> %-10s  Rp %s  (%d move)" % (src, dst, rp(val).strip(), cnt))
except Exception as e:
    print("stock.move read error:", repr(e)[:200])

print("\ngudang (stock.warehouse):")
for w in env["stock.warehouse"].search([]):
    print("   [%d] %-32s code=%s  lot_stock=%s" % (w.id, w.name, w.code, w.lot_stock_id.display_name))


# ===========================================================================
sec("G. PARTNER")
# ===========================================================================
P = env["res.partner"]
print("partner platform (nama mengandung food):")
for x in P.search([("name", "ilike", "food")]):
    print("   [%d] %s" % (x.id, x.name))
print("\npartner terbanyak dipakai order Agustus (top 12):")
cnt = defaultdict(int)
for o in orders:
    if o.partner_id:
        cnt[o.partner_id.name] += 1
for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:12]:
    print("   %-40s %5d order" % (k, v))
print("\nsupplier (supplier_rank > 0), top 10 by id:")
for x in P.search([("supplier_rank", ">", 0)], limit=10):
    print("   [%d] %s" % (x.id, x.name))
print("   total supplier_rank>0 :", P.search_count([("supplier_rank", ">", 0)]))
print("   total customer_rank>0 :", P.search_count([("customer_rank", ">", 0)]))


# ===========================================================================
sec("H. PRODUK & BOM")
# ===========================================================================
PT = env["product.template"]
print("product.template     :", PT.search_count([]))
print("   storable          :", PT.search_count([("is_storable", "=", True)]))
print("   sale_ok           :", PT.search_count([("sale_ok", "=", True)]))
print("product.category     :", env["product.category"].search_count([]))
print("mrp.bom              :", env["mrp.bom"].search_count([]))
print("   tipe phantom      :", env["mrp.bom"].search_count([("type", "=", "phantom")]))
for c in env["product.category"].search([("id", "in", [5, 6, 7, 10, 11])]):
    print("   cat [%d] %-28s cost=%-10s val=%s" % (
        c.id, c.name, c.property_cost_method, c.property_valuation))


# ===========================================================================
sec("I. JURNAL")
# ===========================================================================
for j in env["account.journal"].search([]):
    print("   %-8s %-34s type=%-8s default=%s" % (j.code, j.name[:34], j.type, j.default_account_id.code or "-"))


# ===========================================================================
sec("J. AR / AP TERBUKA PER 31 AGUSTUS")
# ===========================================================================
dom_open = [("parent_state", "=", "posted"), ("date", "<=", AUG2),
            ("account_id.account_type", "in", ["asset_receivable", "liability_payable"]),
            ("full_reconcile_id", "=", False)]
rows = AML._read_group(dom_open, ["account_id", "partner_id"], ["balance:sum", "amount_residual:sum"])
ar = ap = 0.0
for acc, partner, bal, res in rows:
    ar += res if acc.account_type == "asset_receivable" else 0.0
    ap += res if acc.account_type == "liability_payable" else 0.0
    if abs(norm(res)) >= 0.005:
        print("   %-9s %-10s %-34s residual Rp %s" % (
            acc.account_type[:9], acc.code, (partner.display_name or "-")[:34], rp(res).strip()))
print("   TOTAL AR residual: Rp %s" % rp(ar).strip())
print("   TOTAL AP residual: Rp %s" % rp(ap).strip())


# ===========================================================================
sec("K. MODAL DISETOR & EKUITAS")
# ===========================================================================
eq = Acc.search([("account_type", "=", "equity")])
for a in eq:
    bal = sum(norm(x) for x in AML._read_group(
        [("account_id", "=", a.id), ("parent_state", "=", "posted"), ("date", "<=", AUG2)], [], ["balance:sum"])[0])
    print("   %-12s %-44s Rp %s  active=%s" % (a.code, a.name[:44], rp(bal).strip(), a.active))


# ===========================================================================
sec("L. CEK AKTIVITAS JUNI & JULI 2026 (harus kosong)")
# ===========================================================================
for label, d1, d2 in [("Juni", "2026-06-01", "2026-07-01"), ("Juli", "2026-07-01", "2026-08-01")]:
    mv = env["account.move"].search_count([("date", ">=", d1), ("date", "<", d2), ("state", "=", "posted")])
    po = POS.search_count([("date_order", ">=", d1), ("date_order", "<", d2)])
    ss = Sess.search_count([("start_at", ">=", d1), ("start_at", "<", d2)])
    sm = env["stock.move"].search_count([("date", ">=", d1), ("date", "<", d2)])
    print("   %-6s posted move=%d  pos.order=%d  sesi=%d  stock.move=%d" % (label, mv, po, ss, sm))


# ===========================================================================
sec("M. PAJAK (informational — tidak diubah, spec D22)")
# ===========================================================================
for t in env["account.tax"].search([("type_tax_use", "=", "sale")]):
    print("   sale  [%d] %-32s amount=%s  type=%s" % (t.id, t.name[:32], t.amount, t.amount_type))
for t in env["account.tax"].search([("type_tax_use", "=", "purchase")]):
    print("   purch [%d] %-32s amount=%s  type=%s" % (t.id, t.name[:32], t.amount, t.amount_type))


# ===========================================================================
sec("N. INVARIANT — TRIAL BALANCE AGUSTUS (posted)")
# ===========================================================================
rows = AML._read_group(
    [("parent_state", "=", "posted"), ("date", ">=", AUG1), ("date", "<", AUG2X)],
    [], ["debit:sum", "credit:sum"])
deb, cred = norm(rows[0][0]), norm(rows[0][1])
print("debit  : Rp %s" % rp(deb).strip())
print("credit : Rp %s" % rp(cred).strip())
print("diff   : Rp %s  ->  %s" % (rp(deb - cred).strip(), "BALANCE" if abs(deb - cred) < 0.01 else "*** TIDAK BALANCE ***"))
print("jumlah baris move line Agustus:", AML.search_count(dom_post))

# ===========================================================================
sec("O. PAYLOAD DASHBOARD RESMI (sumber kebenaran UI)")
# ===========================================================================
D = env["geprekyukss.dashboard.data"]
d = D.get_dashboard_data(AUG1, AUG2, None)
print("has_data        :", d.get("has_data"))
print("period          :", d.get("period"))
print("prev_period     :", d.get("prev_period"))
s = d.get("summary") or {}
f = d.get("finance") or {}
print("summary.amount_total : Rp %s  (%d order)" % (rp(s.get("amount_total")).strip(), s.get("order_count") or 0))
print("summary.avg_ticket   : Rp %s" % rp(s.get("avg_ticket")).strip())
print("summary.vs           :", s.get("vs"))
print("finance.income_total : Rp %s" % rp(f.get("income_total")).strip())
print("finance.hpp_total    : Rp %s" % rp(f.get("hpp_total")).strip())
print("finance.expense_total: Rp %s" % rp(f.get("expense_total")).strip())
print("finance.net_profit   : Rp %s" % rp(f.get("net_profit")).strip())
print("finance.depreciation : Rp %s" % rp(f.get("depreciation_total")).strip())
bal = f.get("balance") or {}
print("balance              :", {k: round(norm(v), 2) for k, v in bal.items() if isinstance(v, (int, float))})
print("narrative (%d kalimat) :" % len(d.get("narrative") or []))
for line in (d.get("narrative") or []):
    print("   -", line)

print("\nDISCREPANCY CHECK:")
print("   net_profit dashboard - (income-expense) TB = Rp %s" % (
    rp(norm(f.get("net_profit")) - (income - expense)).strip()))

print("\n=== PAYLOAD MEI 2026 (bulan kosong pengganti) ===")
dm = D.get_dashboard_data("2026-05-01", "2026-05-31", None)
print("   has_data:", dm.get("has_data"), "| Mei vs prev:", (dm.get("summary") or {}).get("vs"))

print("\n[RECON SELESAI — read-only, tidak ada perubahan]")
env.cr.rollback()
