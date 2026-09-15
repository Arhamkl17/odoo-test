# -*- coding: utf-8 -*-
"""
juni_juli_10_catering.py — invoice catering B2B Juni & Juli 2026.

Meniru INV/2026/00001 & 00002 (Agustus, total Rp 7.600.000) yang ditemukan saat
menelusuri selisih ledger vs order. Supaya TIDAK memunculkan piutang (§14),
setiap invoice langsung dilunasi **di tanggal yang sama** via transfer Bank BSI,
jadi saldo AR di akhir bulan tetap 0.

Pola Agustus: Dr Piutang Usaha / Cr 4101.02 Penjualan Menu Food, lalu pelunasan
masuk Bank BSI. Di sini pelunasan dibuat di hari yang sama (Agustus: 1-6 hari).

  RUN=1   eksekusi  (default: dry-run)
"""
import os

RUN = os.environ.get("RUN") == "1"
AM = env["account.move"]
cr = env.cr

# (tanggal, partner, keterangan, nominal)
# Keputusan pemilik: catering HANYA di Juni (bulan pemanasan). Juli murni POS,
# supaya tren jumlah order Juli -> Agustus terlihat naik tanpa campuran B2B.
PLAN = [
    ("2026-06-24", "PT Cendana Perkasa", "Catering rapat koordinasi bulanan", 5_500_000),
]


def say(m=""):
    print(m)


say("=" * 78)
say("INVOICE CATERING B2B JUNI & JULI   |   RUN=%s" % RUN)
say("=" * 78)

# --- produk & journal ------------------------------------------------------
print_prod = None
tmpl = AM.search([("name", "=", "INV/2026/00001")], limit=1)
if tmpl:
    for l in tmpl.invoice_line_ids:
        if l.product_id:
            print_prod = l.product_id
            break
if not print_prod:
    print_prod = env["product.product"].search(
        [("available_in_pos", "=", True), ("categ_id.name", "=", "Menu Food")], limit=1)
bnk1 = env["account.journal"].search([("code", "=", "BNK1")], limit=1)
say("produk sumber : %s (id %s)" % (print_prod.display_name, print_prod.id))
say("journal bayar : %s %s" % (bnk1.code, bnk1.name))
say("akun pendapatan produk: %s" % (
    print_prod.property_account_income_id.display_name or "(default kategori)"))

say("")
say("rencana:")
for d, partner, ket, amt in PLAN:
    say("   %s  %-26s %14s  %s" % (d, partner[:26], "{:,.0f}".format(amt), ket))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis.")
    env.cr.rollback()
    raise SystemExit(0)

# --- eksekusi --------------------------------------------------------------
say("")
for d, partner_name, ket, amt in PLAN:
    p = env["res.partner"].search([("name", "=", partner_name)], limit=1)
    if not p:
        p = env["res.partner"].create({"name": partner_name, "customer_rank": 1})
    inv = AM.create({
        "move_type": "out_invoice",
        "partner_id": p.id,
        "invoice_date": d,
        "date": d,
        "invoice_date_due": d,
        "ref": ket,
        "invoice_line_ids": [(0, 0, {
            "product_id": print_prod.id,
            "name": ket,
            "quantity": 1.0,
            "price_unit": amt,
            "tax_ids": [(6, 0, [])],
        })],
    })
    inv.action_post()
    wiz = env["account.payment.register"].with_context(
        active_model="account.move", active_ids=inv.ids
    ).create({
        "journal_id": bnk1.id,
        "payment_date": d,
        "amount": inv.amount_total,
    })
    wiz.action_create_payments()
    say("   %-22s %s  %14s  payment=%s  sisa=%s" % (
        inv.name, d, "{:,.2f}".format(inv.amount_total),
        inv.payment_state, "{:,.2f}".format(inv.amount_residual)))

env.cr.commit()
env.invalidate_all()

# --- verifikasi ------------------------------------------------------------
say("")
say("=" * 78)
say("VERIFIKASI")
for label, last in (("30 Jun", "2026-06-30"), ("31 Jul", "2026-07-31"), ("31 Agu", "2026-08-31")):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0)
                  FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
                  JOIN account_account aa ON aa.id=aml.account_id
                  WHERE am.state='posted' AND am.date<=%s AND aa.account_type='asset_receivable'""",
               (last,))
    piutang = cr.fetchone()[0]
    say("   piutang s/d %s : %18s  %s" % (
        label, "{:,.2f}".format(piutang), "OK" if abs(piutang) < 0.01 else ">>> TIDAK BERSIH"))

cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id
              WHERE am.state='posted' AND am.journal_id=(SELECT id FROM account_journal WHERE code='INV')
                AND am.date>='2026-06-01' AND am.date<'2026-09-01'""")
say("   pendapatan jurnal INV Jun-Agu: %s" % "{:,.2f}".format(-cr.fetchone()[0]))
cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'""")
d_, k_ = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % (
    "{:,.2f}".format(d_), "{:,.2f}".format(k_), "{:,.2f}".format(d_ - k_)))
say("=" * 78)
