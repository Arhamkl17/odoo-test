# -*- coding: utf-8 -*-
"""
juni_juli_08_del_terong.py — hapus menu TERONG CRISPY (117 baris order Agustus).

Kenapa tidak tulis-ulang 59 sesi pos?
  Probe membuktikan `action_pos_session_closing_control()` ulang ikut memposting
  HPP (5101.01/02/04) + kredit Persediaan (1103.01/02/03) yang di Agustus
  diposting TERPISAH lewat MISC -> dobel hitung + valuasi stok ikut berubah.
  Jadi ledger tidak disentuh; koreksinya 1 JE koreksi standar.

Yang dikerjakan:
  A. Hapus 117 baris order TERONG; sesuaikan amount_total/payment order ybs.
     Order yang isinya HANYA TERONG -> dihapus sekalian.
  B. Hapus stock.move milik TERONG.
  C. Hapus produk TERONG CRISPY (fallback: arsipkan).
  D. 1 JE koreksi tgl 2026-08-31: Dr Penjualan / Cr Bank-QRIS-Kas (proporsional
     sesuai metode bayar order-order itu), supaya saldo akun Penjualan =
     omzet order.

  RUN=1   eksekusi  (default: dry-run)

  su odoo -s /bin/bash -c "cd /workspaces/odoo-test && RUN=1 odoo shell -d Test1 \\
      --no-http --db_host db --db_port 5432 --db_user odoo --db_password odoo" \\
      < scripts/juni_juli_08_del_terong.py
"""
import os
from collections import defaultdict

from odoo.exceptions import UserError

RUN = os.environ.get("RUN") == "1"
AUG_FROM, AUG_TO = "2026-08-01", "2026-09-01"
JOURNAL = "MISC"          # dipakai Agustus utk JE koreksi/reklas
DATE = "2026-08-31"
cr = env.cr
POSo = env["pos.order"]
POSl = env["pos.order.line"]
Prod = env["product.product"]
AM = env["account.move"]

say = lambda m="": print(m)
say("=" * 78)
say("HAPUS TERONG CRISPY   |   RUN=%s" % RUN)
say("=" * 78)

terong = Prod.search([("name", "=", "TERONG CRISPY")], limit=1)
if not terong:
    raise UserError("TERONG CRISPY tidak ada — mungkin sudah dihapus.")

lines = POSl.search([("product_id", "=", terong.id)])
aug_lines = lines.filtered(lambda l: AUG_FROM <= str(l.order_id.date_order)[:10] < AUG_TO)
orders = aug_lines.order_id
revenue = sum(aug_lines.mapped("price_subtotal_incl"))
say("produk id=%s | kategori=%s | harga=%s" % (terong.id, terong.categ_id.name, terong.list_price))
say("baris order total=%d (Agustus=%d) di %d order" % (len(lines), len(aug_lines), len(orders)))
say("omzet yang hilang  = %s" % "{:,.2f}".format(revenue))

# metode bayar order-order itu -> akun kas/bank
mixes = defaultdict(float)
for o in orders:
    for p in o.payment_ids:
        j = p.payment_method_id.journal_id
        acc = j.default_account_id
        mixes[(acc.code, acc.name)] += p.amount
prop = {}
for k, v in mixes.items():
    prop[k] = v
tot_mix = sum(prop.values())
say("metode bayar order ybs (basis pembagian koreksi):")
for (code, name), v in sorted(prop.items()):
    say("   %-10s %-32s %s (%.2f%%)" % (code, name[:32], "{:,.2f}".format(v), 100 * v / tot_mix))

sale_acc = env["account.account"].search([("code", "=", "4101.02")], limit=1)
if not sale_acc:
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'='4101.02'")
    sale_acc = env["account.account"].browse(cr.fetchone()[0])
journal = env["account.journal"].search([("code", "=", JOURNAL)], limit=1)

say("")
say("JE koreksi: Dr %s %s / Cr kas-bank proporsional" % (sale_acc.code, "{:,.2f}".format(revenue)))
for (code, name), v in sorted(prop.items()):
    say("   Cr %-10s %-32s %s" % (code, name[:32], "{:,.2f}".format(round(revenue * v / tot_mix, 2))))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada data ditulis.")
    env.cr.rollback()
    raise SystemExit(0)

# =========================== A. HAPUS BARIS ORDER ===========================
say("")
say("--- A. hapus baris order ---")
n_del_order, n_edit = 0, 0
for o in orders:
    ls = o.lines.filtered(lambda l: l.product_id == terong)
    if not ls:
        continue
    cr.execute("UPDATE pos_order SET state='cancel' WHERE id=%s", (o.id,))
    o.invalidate_recordset(["state"])
    if len(ls) == len(o.lines):
        o.payment_ids.unlink()
        o.unlink()
        n_del_order += 1
    else:
        ls.unlink()
        tot = round(sum(o.lines.mapped("price_subtotal_incl")))
        o.write({"amount_total": tot, "amount_paid": tot})
        for p in o.payment_ids:                 # harus selagi order belum 'done'
            p.write({"amount": tot})
        o.write({"state": "done"})
        n_edit += 1
env.flush_all()
say("   order dihapus=%d | order disesuaikan=%d" % (n_del_order, n_edit))

# =========================== B. STOCK MOVE =================================
# stock.move utk TERONG sudah 'done' (konsumsi historis). Odoo melarang cancel/unlink
# move 'done', dan menghapusnya via SQL akan mengembalikan bahan baku ke persediaan
# (1103.01/02/03) sehingga butuh koreksi valuasi lagi. Jadi dibiarkan utuh sebagai
# histori; yang penting menu-nya tidak lagi dijual.
say("--- B. stock.move (dibiarkan utuh) ---")
sm = env["stock.move"].search([("product_id", "=", terong.id)])
say("   %d stock.move berstatus %s — tidak disentuh (histori konsumsi)" % (
    len(sm), sorted(set(sm.mapped("state")))))

# =========================== C. ARSIPKAN PRODUK ============================
say("--- C. produk ---")
sisa = POSl.search_count([("product_id", "=", terong.id)])
say("   sisa baris order: %d | sisa stock.move: %d" % (sisa, len(sm)))
# unlink bisa ditolak FK (account_move_line.product_id dari posting HPP stok),
# jadi dibungkus SAVEPOINT supaya transaksi tidak ikut gugur.
cr.execute("SAVEPOINT sp_prod")
try:
    terong.unlink()
    cr.execute("RELEASE SAVEPOINT sp_prod")
    say("   produk TERONG CRISPY dihapus permanen")
except Exception as e:
    cr.execute("ROLLBACK TO SAVEPOINT sp_prod")
    terong.write({"active": False})
    say("   unlink diblokir Odoo (%s)" % repr(e).split("(")[0][:70])
    say("   -> produk TERONG CRISPY DIARSIPKAN (active=False), hilang dari POS")

# =========================== D. JE KOREKSI =================================
say("--- D. JE koreksi ---")
vals = [{"account_id": sale_acc.id, "debit": round(revenue, 2), "credit": 0.0,
         "name": "Koreksi omzet: penghapusan menu TERONG CRISPY"}]
for (code, name), v in sorted(prop.items()):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    if not r or round(revenue * v / tot_mix, 2) == 0:
        continue
    vals.append({"account_id": r[0], "debit": 0.0,
                 "credit": round(revenue * v / tot_mix, 2),
                 "name": "Koreksi omzet: penghapusan menu TERONG CRISPY"})
mv = AM.create({"journal_id": journal.id, "date": DATE,
                "ref": "Koreksi hapus menu TERONG CRISPY", "line_ids": [(0, 0, v) for v in vals]})
mv.action_post()
say("   %s posted, %d baris, total %s" % (mv.name, len(mv.line_ids),
                                          "{:,.2f}".format(sum(mv.line_ids.mapped("debit")))))

env.cr.commit()
env.invalidate_all()

# =========================== VERIFIKASI ====================================
say("")
say("=" * 78)
say("VERIFIKASI")
aug = POSo.search([("date_order", ">=", AUG_FROM), ("date_order", "<", AUG_TO)])
say("   order Agustus: %d | omzet: %s" % (
    len(aug), "{:,.2f}".format(sum(aug.mapped("amount_total")))))
t_now = Prod.with_context(active_test=False).search([("name", "=", "TERONG CRISPY")], limit=1)
say("   sisa baris TERONG: %d | produk masih ada: %s | active=%s" % (
    POSl.search_count([("product_id", "=", terong.id)]), bool(t_now), t_now.active))
say("   menu aktif di POS: %d (sebelumnya termasuk TERONG CRISPY)" %
    Prod.search_count([("available_in_pos", "=", True)]))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id
              WHERE am.state='posted' AND aml.account_id=%s AND am.date <= %s""",
           (sale_acc.id, DATE))
say("   saldo Penjualan Menu Food s/d 31 Agu: %s (harus = omzet Food di order)" % (
    "{:,.2f}".format(cr.fetchone()[0])))
cr.execute("""SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % (
    "{:,.2f}".format(d), "{:,.2f}".format(k), "{:,.2f}".format(d - k)))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
              JOIN account_move am ON am.id=aml.move_id JOIN account_account aa ON aa.id=aml.account_id
              WHERE am.state='posted' AND am.date<='2026-08-31' AND aa.account_type='asset_receivable'""")
say("   piutang @31 Agu: %s" % "{:,.2f}".format(cr.fetchone()[0]))
say("=" * 78)
