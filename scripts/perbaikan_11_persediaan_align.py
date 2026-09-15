# -*- coding: utf-8 -*-
"""perbaikan_11_persediaan_align.py — F2: samakan nilai Persediaan GL dengan sub-ledger stok

Masalah (temuan F2 INSPEKSI_SISTEM_2026-09-15.md):
  * Neraca (GL) menunjukkan persediaan 244.899.267,57 — sub-ledger stok
    (`stock.quant.value`) hanya 241.605.389,15 → selisih ±3,29 jt.
  * Penyebab: (a) saldo awal 19 Jun diposting ke akun `11300180 Inventory`
    (244.900.000, dibulatkan) padahal seluruh alur pembelian/konsumsi memakai
    akun kategori `1103.01/02/03`; (b) saldo awal ikut menilai `NASI` & `ES TEH`
    (menu `consu` non-storable, nilai Odoo = 0) sebesar 3.271.866,10;
    (c) residu pembulatan alur FIFO ±22 rb.

Yang dilakukan skrip ini (idempotent — bisa dijalankan ulang kapan saja):
  1. hitung target tiap akun persediaan = Σ `stock.quant.value` produk kategori
     yang memakai akun itu (produk non-storable otomatis bernilai 0, sesuai Odoo);
  2. akun `11300180 Inventory` di-nol-kan (saldo awalnya dipindahkan ke akun kategori);
  3. selisihnya dibebankan ke `31510010 Past Profit & Loss` (koreksi saldo awal /
     laba ditahan — BUKAN beban periode berjalan, jadi laba rugi tidak terpengaruh);
  4. setelah selesai: Persediaan tab == Neraca == GL, dan Neraca tetap seimbang.

Jalankan (default = DRY-RUN):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
    --db_user odoo --db_password odoo --log-level=warn" < scripts/perbaikan_11_persediaan_align.py

Eksekusi:
  RUN=1 su odoo -s /bin/bash -c "odoo shell -d Test1 ..." < scripts/perbaikan_11_persediaan_align.py

Env opsional:
  DATE=2026-06-19      tanggal JE koreksi (default: tanggal saldo awal)
  CUTOFF=2026-08-31    batas tanggal perhitungan saldo GL (default: seluruh data)
"""
import os
from collections import defaultdict

RUN = os.environ.get("RUN") == "1"
DATE = os.environ.get("DATE", "2026-06-19")
CUTOFF = os.environ.get("CUTOFF", "2026-12-31")

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

cr = env.cr
Quant = env["stock.quant"]
Account = env["account.account"].with_context(active_test=False)
AM = env["account.move"]

OPENING_INVENTORY_CODE = "11300180"   # akun saldo awal (harus jadi 0)
RETAINED_CODE = "31510010"            # Past Profit & Loss
REF = "KOREKSI-PERSEDIAAN-AWAL"

say("=" * 110)
say("F2 — SAMAKAN PERSEDIAAN GL DENGAN SUB-LEDGER STOK | RUN=%s | tanggal JE=%s" % (RUN, DATE))
say("=" * 110)

# ------------------------------------------------------------ 1) target per akun
say("")
say("[1] Target tiap akun persediaan = Σ stock.quant.value kategori terkait")
quant_by_cat = defaultdict(float)
for categ, val, qty in Quant._read_group(
        [("location_id.usage", "=", "internal")], ["product_id.categ_id"], ["value:sum", "quantity:sum"]):
    quant_by_cat[categ.id] = float(val or 0.0)

acc_target = defaultdict(float)
acc_cats = defaultdict(list)
for cat in env["product.category"].with_context(active_test=False).search([]):
    acc = cat.property_stock_valuation_account_id
    if not acc:
        continue
    acc_target[acc.id] += quant_by_cat.get(cat.id, 0.0)
    if quant_by_cat.get(cat.id):
        acc_cats[acc.id].append(cat.name)

def acc_id_by_code(code):
    """Akun by kode — code Odoo 19 company-dependent (`code_store` jsonb),
    jadi dicari via SQL supaya tidak bergantung bentuk domain ORM."""
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1' = %s", (code,))
    r = cr.fetchone()
    return r[0] if r else None


opening_acc_id = acc_id_by_code(OPENING_INVENTORY_CODE)
if opening_acc_id:
    acc_target[opening_acc_id] = 0.0   # saldo awal dipindahkan ke akun kategori

# ------------------------------------------------------------ 2) saldo GL vs target
say("")
say("%-10s %-42s %18s %18s %16s" % ("KODE", "AKUN", "SALDO GL", "TARGET (STOK)", "SELISIH"))
say("-" * 110)
rows = []
for acc_id, target in sorted(acc_target.items(), key=lambda x: Account.browse(x[0]).code or ""):
    acc = Account.browse(acc_id)
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
                  WHERE am.state='posted' AND aml.account_id=%s AND aml.date <= %s""", (acc_id, CUTOFF))
    bal = float(cr.fetchone()[0] or 0.0)
    delta = target - bal
    rows.append((acc, bal, target, delta))
    say("%-10s %-42s %18s %18s %16s%s" % (acc.code, (acc.name or "")[:42], money(bal), money(target), money(delta),
                                          "" if abs(delta) < 0.01 else "  <== koreksi"))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND aa.account_type = 'asset_current'""")
gl_total = float(cr.fetchone()[0] or 0.0)
quant_total = sum(quant_by_cat.values())
say("-" * 110)
say("%-53s %18s %18s %16s" % ("TOTAL PERSEDIAAN (akun di atas)", money(sum(r[1] for r in rows)),
                              money(sum(r[2] for r in rows)), money(sum(r[3] for r in rows))))
say("%-53s %18s" % ("Σ stock.quant.value (lokasi internal)", money(quant_total)))
say("%-53s %18s" % ("GL asset_current total (termasuk Outstanding Receipts)", money(gl_total)))

# Nilai quant punya pecahan sub-sen → tiap baris dibulatkan 2 desimal, dan baris
# penyeimbang dihitung dari jumlah SEN dari baris yang sudah dibulatkan, supaya
# entry pasti seimbang persis (kalau tidak: "The entry is not balanced").
adjust = []
total_cents = 0
for (acc, bal, target, delta) in rows:
    cents = int(round(float(delta) * 100))
    if cents == 0:
        continue
    adjust.append((acc, cents))
    total_cents += cents
total_delta = total_cents / 100.0
say("")
say("  Total koreksi = %s (offset ke %s)" % (money(total_delta), RETAINED_CODE))

# ------------------------------------------------------------ 3) JE
say("")
say("[2] JE koreksi yang akan dibuat (tanggal %s, ref %s):" % (DATE, REF))
for acc, cents in adjust:
    say("    %s %-10s %-42s %18s" % ("Dr" if cents > 0 else "Cr", acc.code, (acc.name or "")[:42], money(abs(cents) / 100.0)))
say("    %s %-10s %-42s %18s" % ("Cr" if total_cents > 0 else "Dr", RETAINED_CODE, "Past Profit & Loss", money(abs(total_cents) / 100.0)))

if not adjust:
    say("")
    say("  Tidak ada selisih — persediaan sudah selaras. Selesai.")
    env.cr.rollback()
    import sys
    sys.exit(0)

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis. Jalankan RUN=1 untuk eksekusi.")
    env.cr.rollback()
    import sys
    sys.exit(0)

journal = env["account.journal"].search([("code", "=", "MISC"), ("company_id", "=", env.company.id)], limit=1)
retained = Account.browse(acc_id_by_code(RETAINED_CODE))
lines = []
for acc, cents in adjust:
    amt = cents / 100.0
    lines.append((0, 0, {
        "account_id": acc.id,
        "name": "%s — %s" % (REF, acc.name),
        "debit": amt if amt > 0 else 0.0,
        "credit": -amt if amt < 0 else 0.0,
    }))
offset_amt = -total_delta
lines.append((0, 0, {
    "account_id": retained.id,
    "name": "%s — koreksi saldo awal persediaan" % REF,
    "debit": offset_amt if offset_amt > 0 else 0.0,
    "credit": -offset_amt if offset_amt < 0 else 0.0,
}))
am = AM.create({
    "journal_id": journal.id,
    "date": DATE,
    "ref": REF,
    "line_ids": lines,
})
am.action_post()
env.cr.commit()
say("")
say("  JE dibuat & diposting: %s (%s) tanggal %s" % (am.name, REF, DATE))
for l in am.line_ids:
    say("    %s %-10s %-42s %18s %18s" % (l.account_id.code, "", (l.account_id.name or "")[:42], money(l.debit), money(l.credit)))

# ------------------------------------------------------------ 4) verifikasi
say("")
say("[3] Verifikasi ulang")
ok = True
for acc, _bal, target, _delta in rows:
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
                  WHERE am.state='posted' AND aml.account_id=%s AND aml.date <= %s""", (acc.id, CUTOFF))
    bal = float(cr.fetchone()[0] or 0.0)
    mark = "OK" if abs(bal - target) < 0.01 else ">>>"
    if mark != "OK":
        ok = False
    say("    %-10s %-42s saldo %18s target %18s %s" % (acc.code, (acc.name or "")[:42], money(bal), money(target), mark))

cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND aa.account_type = 'asset_current'""")
gl_after = float(cr.fetchone()[0] or 0.0)
D = env["geprekyukss.dashboard.data"]
ops = D._ops_warehouse("2026-08-01", "2026-08-31")
inv = ops["inventory"]
say("")
say("    GL asset_current total   : %18s" % money(gl_after))
say("    Persediaan dashboard     : %18s  (per gudang: %s)" % (
    money(inv["total"]), ", ".join("%s %s" % (r["warehouse"], money(r["value"])) for r in inv["per_warehouse"])))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND aa.account_type IN
                    ('asset_cash','asset_receivable','asset_current','asset_prepayments','asset_fixed')""")
assets = float(cr.fetchone()[0] or 0.0)
cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND aa.account_type IN ('liability_payable','liability_current')""")
liab = float(cr.fetchone()[0] or 0.0)
cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND aa.account_type IN ('equity','equity_unaffected','income','income_other',
                   'expense','expense_direct_cost','expense_depreciation')""")
eq_ni = float(cr.fetchone()[0] or 0.0)
say("    Neraca: aset %s = kewajiban %s + ekuitas+laba %s  -> selisih %s %s" % (
    money(assets), money(-liab), money(-eq_ni), money(assets + liab + eq_ni),
    "OK" if abs(assets + liab + eq_ni) < 0.01 else ">>>"))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              WHERE am.state='posted'""")
d, k = cr.fetchone()
say("    TB debit %s = credit %s (diff %s)" % (money(d), money(k), money(float(d or 0) - float(k or 0))))
say("")
say("HASIL: %s" % ("persediaan GL == sub-ledger stok ✔" if ok else "MASIH ADA SELISIH — periksa di atas"))
say("=" * 110)
