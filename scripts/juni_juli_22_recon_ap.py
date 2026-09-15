# -*- coding: utf-8 -*-
"""juni_juli_22_recon_ap.py — bedah isi akun HUTANG (READ-ONLY)."""
from dateutil.relativedelta import relativedelta
from odoo import fields

cr = env.cr
say = lambda m="": print(m)
LIAB = ("liability_payable", "liability_current", "liability_non_current", "liability_credit_card")

say("=" * 100)
say("A. SALDO akun hutang kumulatif per akhir bulan")
for last in ("2026-06-30", "2026-07-31", "2026-08-31"):
    say("   --- s/d %s ---" % last)
    cr.execute("""
        SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'),
               aa.account_type, SUM(aml.balance), COUNT(*)
          FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
          JOIN account_account aa ON aa.id = aml.account_id
         WHERE am.state='posted' AND am.date <= %s AND aa.account_type IN %s
         GROUP BY 1,2,3 HAVING ABS(SUM(aml.balance)) > 0.01 ORDER BY 1""", (last, LIAB))
    for kode, nama, tipe, bal, n in cr.fetchall():
        say("      %-12s %-40s %-18s %18s  (%d baris)" % (
            kode, (nama or "")[:40], tipe, "{:,.2f}".format(bal), n))

say("")
say("B. MUTASI hutang per bulan (kredit = hutang bertambah, debit = dibayar)")
for a, b, lab in (("2026-06-01", "2026-07-01", "Jun"),
                  ("2026-07-01", "2026-08-01", "Jul"),
                  ("2026-08-01", "2026-09-01", "Agu")):
    cr.execute("""
        SELECT COALESCE(SUM(aml.credit),0), COALESCE(SUM(aml.debit),0)
          FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
          JOIN account_account aa ON aa.id = aml.account_id
         WHERE am.state='posted' AND am.date >= %s AND am.date < %s
           AND aa.account_type IN %s""", (a, b, LIAB))
    k, d = cr.fetchone()
    say("   %-4s kredit(+utang)=%18s | debit(bayar)=%18s | net=%18s" % (
        lab, "{:,.2f}".format(k), "{:,.2f}".format(d), "{:,.2f}".format(k - d)))

say("")
say("C. DARI MANA hutang itu datang (kredit per asal) — 3 bulan")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') bln,
           CASE WHEN aml.name ILIKE 'HPP-BOM%%' THEN 'P7: pembelian stok (baru)'
                WHEN am.move_type = 'in_invoice' THEN 'vendor bill ' || aj.code
                ELSE 'lain: ' || aj.code END AS asal,
           COUNT(*), SUM(aml.credit)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
      JOIN account_journal aj ON aj.id = am.journal_id
     WHERE am.state='posted' AND aa.account_type IN %s AND aml.credit > 0
       AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
     GROUP BY 1,2 ORDER BY 4 DESC LIMIT 14""", (LIAB,))
for bln, asal, n, k in cr.fetchall():
    say("   %s %-34s n=%-5d %18s" % (bln, (asal or "")[:34], n, "{:,.2f}".format(k or 0)))

say("")
say("D. STATUS vendor bill lama (metode HPP Agustus) — sudah dibatalkan?")
cr.execute("""
    SELECT am.state, COUNT(*), COALESCE(SUM(am.amount_total),0)
      FROM account_move am
     WHERE am.move_type='in_invoice' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
     GROUP BY 1""")
for st, n, tot in cr.fetchall():
    say("   state=%-9s n=%-5d total=%18s" % (st, n, "{:,.2f}".format(tot or 0)))

say("")
say("E. Berapa yang SUDAH dibayar ke vendor selama 3 bulan?")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM'), aj.code, COUNT(*), SUM(aml.debit)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
      JOIN account_journal aj ON aj.id = am.journal_id
     WHERE am.state='posted' AND aa.account_type IN %s AND aml.debit > 0
       AND am.date >= '2026-06-01' AND am.date < '2026-09-01'
     GROUP BY 1,2 ORDER BY 1,3 DESC""", (LIAB,))
rows_ = cr.fetchall()
if not rows_:
    say("   (TIDAK ADA pembayaran ke vendor sama sekali)")
for bln, jr, n, d in rows_:
    say("   %s %-6s n=%-5d %18s" % (bln, jr, n, "{:,.2f}".format(d or 0)))
say("=" * 100)
env.cr.rollback()
