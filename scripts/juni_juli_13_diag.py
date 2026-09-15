# -*- coding: utf-8 -*-
"""juni_juli_13_diag.py — telusuri beban & akun kas Juni/Juli (READ-ONLY)."""
from odoo import fields
cr = env.cr
say = lambda m="": print(m)

for label, a, b in (("Jun", "2026-06-01", "2026-07-01"), ("Jul", "2026-07-01", "2026-08-01")):
    say("=" * 88)
    say("[%s] SALDO per akun (posted, >= %s < %s)" % (label, a, b))
    cr.execute("""
        SELECT aa.code_store->>'1' AS kode, aa.account_type AS tipe,
               COALESCE(aa.name->>'en_US', aa.name->>'1') AS nama,
               SUM(aml.balance) AS saldo, COUNT(*) AS baris
          FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
          JOIN account_account aa ON aa.id=aml.account_id
         WHERE am.state='posted' AND am.date >= %s AND am.date < %s
         GROUP BY 1,2,3 HAVING ABS(SUM(aml.balance)) > 0.01
         ORDER BY ABS(SUM(aml.balance)) DESC LIMIT 18""", (a, b))
    say("    %-12s %-22s %-36s %18s %6s" % ("kode", "tipe", "nama", "saldo", "baris"))
    for kode, tipe, nama, saldo, baris in cr.fetchall():
        say("    %-12s %-22s %-36s %18s %6d" % (kode, tipe, (nama or "")[:36],
                                                 "{:,.2f}".format(saldo), baris))

    say("")
    say("[%s] AKUN KAS/BANK — saldo kumulatif s/d akhir bulan" % label)
    last = (fields.Date.to_date(b).replace(day=1) if False else b)
    cr.execute("""
        SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'),
               SUM(aml.balance), COUNT(*)
          FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
          JOIN account_account aa ON aa.id=aml.account_id
         WHERE am.state='posted' AND am.date < %s AND aa.account_type IN ('asset_cash','asset_current')
           AND (aa.code_store->>'1' LIKE '110%%')
         GROUP BY 1,2 ORDER BY 1""", (b,))
    for kode, nama, saldo, baris in cr.fetchall():
        say("    %-12s %-40s %18s %6d" % (kode, (nama or "")[:40], "{:,.2f}".format(saldo), baris))
say("=" * 88)
env.cr.rollback()
