# -*- coding: utf-8 -*-
"""READ-ONLY: apakah pembelian tunai Rp 347,5 jt membuat Bank BSI minus?"""
cr = env.cr
say = lambda m="": print(m)


def aid(code):
    cr.execute("SELECT id FROM account_account WHERE code_store->>'1'=%s LIMIT 1", (code,))
    r = cr.fetchone()
    return r[0] if r else None


def rows(sql, p=()):
    cr.execute(sql, p)
    return cr.fetchall()


say("=" * 100)
say("1) SALDO HARIAN BANK BSI (1101.01) + KAS + QRIS  — Juni..Agu")
say("=" * 100)
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM-DD') d,
           SUM(CASE WHEN aa.code_store->>'1'='1101.01' THEN aml.balance ELSE 0 END) bank,
           SUM(CASE WHEN aa.code_store->>'1' LIKE '1101%' AND aa.code_store->>'1'<>'1101.01'
                    THEN aml.balance ELSE 0 END) kas_lain
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND am.date>='2026-06-01' AND aa.code_store->>'1' LIKE '1101%'
     GROUP BY 1 ORDER BY 1""")
run = 0.0
prev_m = None
for d, bank, kas in cr.fetchall():
    m = d[:7]
    if m != prev_m:
        say("   --- %s (kumulatif s/d bulan ini) ---" % m)
        prev_m = m
    run += (bank or 0)
say("   TOTAL saldo 1101.01 (semua periode) = %s" % "{:,.2f}".format(run))

say("")
say("2) MUTASI BANK BSI per BULAN")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, SUM(aml.debit) dr, SUM(aml.credit) cr, SUM(aml.balance) net
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01'
     GROUP BY 1 ORDER BY 1""")
for m, dr, cr_, net in cr.fetchall():
    say("   %s  masuk=%16s  keluar=%16s  net=%16s" % (m, "{:,.0f}".format(dr), "{:,.0f}".format(cr_), "{:,.0f}".format(net)))

say("")
say("3) MUTASI BERDASARKAN JENIS (semua akun kas/bank 11xx) per BULAN")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m,
           SUM(CASE WHEN aa.code_store->>'1' LIKE '1101%' OR aa.code_store->>'1' LIKE '1102%'
                    THEN aml.balance ELSE 0 END) kasbank
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted'
     GROUP BY 1 ORDER BY 1""")
for m, kb in cr.fetchall():
    say("   %s  net kas+bank = %16s" % (m, "{:,.0f}".format(kb)))

say("")
say("4) EKUITAS / MODAL (3xxx) per akhir bulan")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, aa.code_store->>'1' code, aa.name->>'en_US' nm,
           SUM(aml.balance) bal
      FROM account_move_line aml
      JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1' LIKE '3%'
     GROUP BY 1,2,3 ORDER BY 2,1""")
for m, code, nm, bal in cr.fetchall():
    say("   %s  %-10s %-34s %16s" % (m, code, (nm or "")[:34], "{:,.0f}".format(bal)))

say("")
say("5) APA YANG DIKREDIT OLEH 141 JE PEMBELIAN? (semua baris kredit)")
cr.execute("""
    SELECT aa.code_store->>'1', aa.name->>'en_US', COUNT(*), SUM(aml.credit)
      FROM stock_move sm JOIN account_move am ON am.id=sm.account_move_id
      JOIN account_move_line aml ON aml.move_id=am.id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE sm.origin LIKE 'HPP-BOM beli%' AND aml.credit>0
     GROUP BY 1,2 ORDER BY 4 DESC""")
for code, nm, n, cr_ in cr.fetchall():
    say("   %-10s %-40s n=%-4d %16s" % (code, (nm or "")[:40], n, "{:,.0f}".format(cr_)))

say("")
say("6) DEBIT JE PEMBELIAN (sisi persediaan)")
cr.execute("""
    SELECT aa.code_store->>'1', COUNT(*), SUM(aml.debit)
      FROM stock_move sm JOIN account_move am ON am.id=sm.account_move_id
      JOIN account_move_line aml ON aml.move_id=am.id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE sm.origin LIKE 'HPP-BOM beli%' AND aml.debit>0
     GROUP BY 1 ORDER BY 3 DESC""")
for code, n, dr in cr.fetchall():
    say("   %-10s n=%-4d %16s" % (code, n, "{:,.0f}".format(dr)))

say("=" * 100)
env.cr.rollback()
