# -*- coding: utf-8 -*-
"""READ-ONLY: neraca ringkas Juni-Agu + saldo harian minimum bank."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 104)
say("TRIAL BALANCE RINGKAS per AKUN (Juni..Sep 2026, posted)")
say("=" * 104)
cr.execute("""
    SELECT aa.code_store->>'1' code, aa.name->>'en_US' nm, aa.account_type at,
           COALESCE(SUM(aml.debit),0) dr, COALESCE(SUM(aml.credit),0) cr,
           COALESCE(SUM(aml.balance),0) bal
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted'
     GROUP BY 1,2,3 HAVING COALESCE(SUM(aml.balance),0)<>0
     ORDER BY 4 DESC""")
tot_d = tot_k = 0.0
for code, nm, at, dr, cr_, bal in cr.fetchall():
    tot_d += dr
    tot_k += cr_
    say("   %-11s %-36s %-22s dr=%15s cr=%15s SALDO=%16s" % (
        code or "-", (nm or "")[:36], (at or "")[:22],
        "{:,.0f}".format(dr), "{:,.0f}".format(cr_), "{:,.0f}".format(bal)))
say("   TOTAL debit=%s credit=%s diff=%s" % ("{:,.2f}".format(tot_d), "{:,.2f}".format(tot_k),
                                             "{:,.2f}".format(tot_d - tot_k)))

say("")
say("=" * 104)
say("SALDO HARIAN KUMULATIF 1101.01 (minimum terlihat di sini)")
say("=" * 104)
cr.execute("""
    SELECT am.date, SUM(aml.balance)
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01'
     GROUP BY 1 ORDER BY 1""")
run = 0.0
mn = None
mn_d = None
for d, bal in cr.fetchall():
    run += bal
    if mn is None or run < mn:
        mn = run
        mn_d = d
say("   jumlah titik tanggal : %d" % 1)
say("   SALDO AKHIR          : %s" % "{:,.2f}".format(run))
say("   SALDO TERENDAH       : %s  (pada %s)" % ("{:,.2f}".format(mn), mn_d))

say("")
say("BERAPA LAGI YANG DIBUTUHKAN kalau 347,5 jt dibayar tunai:")
say("   saldo bank setelah bayar = %s" % "{:,.2f}".format(run - 347479045.46))
env.cr.rollback()
