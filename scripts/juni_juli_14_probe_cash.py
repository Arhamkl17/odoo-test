# -*- coding: utf-8 -*-
"""juni_juli_14_probe_cash.py — kenapa selisih kas Juni/Juli tidak nol? (READ-ONLY)"""
from odoo import fields
cr = env.cr
Sess = env["pos.session"]
say = lambda m="": print(m)


def dump(tag, sessions):
    say("=" * 100)
    say(tag)
    say("%-6s %-24s %-20s %12s %12s %12s %12s %12s" % (
        "id", "config", "mulai", "saldo_awal", "end", "end_real", "diff", "kas_masuk"))
    for s in sessions:
        say("%-6s %-24s %-20s %12s %12s %12s %12s %12s" % (
            s.id, s.config_id.name, str(s.start_at)[:19],
            "{:,.0f}".format(s.cash_register_balance_start or 0),
            "{:,.0f}".format(s.cash_register_balance_end or 0),
            "{:,.0f}".format(s.cash_register_balance_end_real or 0),
            "{:,.0f}".format(s.cash_register_difference or 0),
            "{:,.0f}".format(s._get_cash_in() if hasattr(s, "_get_cash_in") else 0)))


for a, b, tag in (("2026-06-01", "2026-07-01", "JUNI (5 sesi pertama)"),
                  ("2026-07-01", "2026-08-01", "JULI (5 sesi pertama)"),
                  ("2026-08-01", "2026-09-01", "AGUSTUS (referensi, 5 sesi pertama)")):
    ss = Sess.search([("start_at", ">=", a), ("start_at", "<", b)], order="start_at", limit=5)
    dump(tag, ss)

say("=" * 100)
say("BRUTO: total selisih kas per bulan (akun beban 6101.23 baris 'Perbedaan kas')")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') AS bln, aa.code_store->>'1', aml.name,
           COUNT(*), SUM(aml.debit), SUM(aml.credit)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1' = '6101.23'
       AND aml.name ILIKE 'Perbedaan kas%%'
     GROUP BY 1,2,3 ORDER BY 1""")
for bln, kode, nm, n, d, k in cr.fetchall():
    say("   %s %s  n=%-4d debit=%18s credit=%18s  [%s]" % (
        bln, kode, n, "{:,.2f}".format(d or 0), "{:,.2f}".format(k or 0), (nm or "")[:40]))

say("")
say("PEMBAYARAN TUNAI per bulan (metode type='cash'):")
cr.execute("""
    SELECT to_char(o.date_order,'YYYY-MM'), pm.name, pm.type, COUNT(*), SUM(p.amount)
      FROM pos_payment p JOIN pos_order o ON o.id = p.pos_order_id
      JOIN pos_payment_method pm ON pm.id = p.payment_method_id
     WHERE o.date_order >= '2026-06-01' AND o.date_order < '2026-09-01'
     GROUP BY 1,2,3 ORDER BY 1,2""")
for bln, nm, tp, n, amt in cr.fetchall():
    say("   %s %-26s type=%-10s n=%-5d %18s" % (bln, nm, tp, n, "{:,.2f}".format(amt or 0)))
say("=" * 100)
env.cr.rollback()
