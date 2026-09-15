# -*- coding: utf-8 -*-
"""
juni_juli_28_cash_purchase_reclass.py — ubah pembelian bahan jadi TUNAI.

Masalah: 141 JE pembelian ber-origin `HPP-BOM beli ...` mengkredit 2101.01 Utang Usaha
tanpa vendor/nomor/jatuh tempo -> neraca menunjukkan utang Rp 347 jt yang tidak nyata.

Odoo menolak `_action_cancel()` pada stock.move berstatus Done
("You cannot cancel a stock move that has been set to 'Done'"), jadi stock move TIDAK
disentuh sama sekali (kuantitas & valuasi persediaan tetap utuh). Yang diperbaiki hanya
sisi akuntansinya:

    kredit 2101.01 Utang Usaha   ->   1101.01 Bank BSI

Lokasi `BTL/Vendor` sudah diarahkan ke 1101.01, jadi pembelian berikutnya otomatis tunai.

  RUN=1  eksekusi (default dry-run)
"""
import os

RUN = os.environ.get("RUN") == "1"
ORIG = "HPP-BOM beli"
cr = env.cr
AM = env["account.move"]
AA = env["account.account"]
say = lambda m="": print(m)


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


AP = aid("2101.01")
BANK = aid("1101.01")
say("=" * 96)
say("PEMBELIAN BAHAN -> TUNAI   |   RUN=%s" % RUN)
say("   utang (2101.01) id=%s | bank (1101.01) id=%s" % (AP, BANK))
say("=" * 96)

cr.execute("""
    SELECT DISTINCT am.id, am.name, am.date, am.state
      FROM stock_move sm JOIN account_move am ON am.id = sm.account_move_id
     WHERE sm.origin LIKE %s ORDER BY am.id""", (ORIG + "%",))
jes = cr.fetchall()
say("JE pembelian ditemukan: %d" % len(jes))

tot = 0.0
n_ok = n_skip = 0
for mid, nm, dt, st in jes:
    m = AM.browse(mid)
    lines = m.line_ids.filtered(lambda l: l.account_id.id == AP)
    if not lines:
        n_skip += 1
        continue
    amt = sum(lines.mapped("credit"))
    tot += amt
    if not RUN:
        continue
    try:
        if m.state == "posted":
            m.button_draft()
        for l in lines:
            l.write({"account_id": BANK,
                     "name": "Pembelian bahan tunai via Bank BSI"})
        m.action_post()
        n_ok += 1
    except Exception as e:
        say("   GAGAL %s -> %s" % (nm, repr(e)[:110]))
    if n_ok % 40 == 0 and n_ok:
        env.cr.commit()
        say("      ... %d JE diproses" % n_ok)
if RUN:
    env.cr.commit()

say("")
say("   total dipindahkan dari Utang Usaha ke Bank: %s" % "{:,.2f}".format(tot))
say("   berhasil=%d | dilewati=%d" % (n_ok, n_skip))

say("")
say("VERIFIKASI")
for code in ("2101.01", "1101.01", "1103.01", "1103.02", "1103.03"):
    cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                    JOIN account_move am ON am.id=aml.move_id
                    JOIN account_account aa ON aa.id=aml.account_id
                   WHERE am.state='posted' AND aa.code_store->>'1'=%s""", (code,))
    say("   %-10s saldo = %18s" % (code, "{:,.2f}".format(cr.fetchone()[0])))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
                JOIN account_move am ON am.id=aml.move_id
                JOIN account_account aa ON aa.id=aml.account_id
               WHERE am.state='posted' AND aa.account_type='liability_payable'""")
say("   TOTAL hutang (liability_payable) = %s" % "{:,.2f}".format(cr.fetchone()[0]))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
                FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
               WHERE am.state='posted'""")
d, k = cr.fetchone()
say("   TB debit=%s credit=%s diff=%s" % ("{:,.2f}".format(d), "{:,.2f}".format(k),
                                          "{:,.2f}".format(d - k)))
say("=" * 96)
