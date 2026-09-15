# -*- coding: utf-8 -*-
"""READ-ONLY: pola setoran QRIS yang sudah ada + isi 2 mutasi bank 500rb 20 Juni."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 100)
say("1) JE yang sudah mengkredit 1101.02 QRIS (pola setoran yang ada)")
cr.execute("""
    SELECT am.date, am.name, am.ref, aa.code_store->>'1' code, aml.debit, aml.credit
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.02' AND aml.credit>0
     ORDER BY am.date""")
for d, nm, ref, code, dr, cr_ in cr.fetchall():
    say("   %s %-22s ref=%-18s lawan=%-9s cr=%14s" % (d, nm, (ref or "")[:18], code, "{:,.0f}".format(cr_)))
    cr2 = env.cr
    cr2.execute("""SELECT aa2.code_store->>'1', aa2.name->>'en_US', aml2.debit
                     FROM account_move_line aml2 JOIN account_account aa2 ON aa2.id=aml2.account_id
                    WHERE aml2.move_id=%s AND aa2.code_store->>'1'<>'1101.02'""", (int(nm and 0) or 0,))

say("")
say("2) DUA MUTASI KREDIT 500.000 DI BANK 20 JUNI")
cr.execute("""
    SELECT am.id, am.date, am.name, am.ref, aml.credit, aml.name
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01'
       AND am.date='2026-06-20' AND aml.credit>0 ORDER BY aml.id""")
for mid, d, nm, ref, cr_, label in cr.fetchall():
    say("   %s %-22s ref=%-20s cr=%12s  label=%s" % (d, nm, (ref or "")[:20], "{:,.0f}".format(cr_), label))
    cr.execute("""SELECT aa.code_store->>'1', aa.name->>'en_US', aml.debit, aml.credit
                    FROM account_move_line aml JOIN account_account aa ON aa.id=aml.account_id
                   WHERE aml.move_id=%s ORDER BY aml.id""", (mid,))
    for code, acct, dr, cr2 in cr.fetchall():
        say("        %-10s %-34s dr=%14s cr=%14s" % (code, (acct or "")[:34],
                                                      "{:,.0f}".format(dr), "{:,.0f}".format(cr2)))

say("")
say("3) SEMUA AKUN KAS/BANK 11xx & 1111xx yang bersaldo")
cr.execute("""
    SELECT aa.code_store->>'1', aa.name->>'en_US', aa.account_type, aa.id, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND (aa.code_store->>'1' LIKE '11%')
     GROUP BY 1,2,3,4 HAVING SUM(aml.balance)<>0 ORDER BY 5 DESC""")
for code, nm, at, i, bal in cr.fetchall():
    say("   id=%-5s %-11s %-30s %-24s %16s" % (i, code, (nm or "")[:30], at, "{:,.0f}".format(bal)))

say("")
say("4) TOTAL ASET LANCAR vs TOTAL ASET")
cr.execute("""
    SELECT aa.account_type, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' GROUP BY 1 ORDER BY 1""")
for at, bal in cr.fetchall():
    say("   %-24s %18s" % (at, "{:,.2f}".format(bal)))
env.cr.rollback()
