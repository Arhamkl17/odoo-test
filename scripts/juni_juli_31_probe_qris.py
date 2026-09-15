# -*- coding: utf-8 -*-
"""READ-ONLY: sebaran QRIS per tanggal + tanggal gelombang pembelian bahan."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 100)
say("1) AKUN 1101.02 QRIS — mutasi per BULAN")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, SUM(aml.debit) dr, SUM(aml.credit) cr
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.02'
     GROUP BY 1 ORDER BY 1""")
for m, dr, cr_ in cr.fetchall():
    say("   %s  masuk=%16s  keluar=%16s" % (m, "{:,.0f}".format(dr), "{:,.0f}".format(cr_)))

say("")
say("2) QRIS masuk per TANGGAL (kumulatif dalam bulan)")
cr.execute("""
    SELECT am.date, SUM(aml.debit) dr
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.02' AND aml.debit>0
     GROUP BY 1 ORDER BY 1""")
kum = {}
for d, dr in cr.fetchall():
    kum.setdefault(d.strftime("%Y-%m"), []).append((d, dr))
for m in sorted(kum):
    items = kum[m]
    tot = sum(x[1] for x in items)
    say("   %s  n=%d  total=%16s  (pertama %s, terakhir %s)" % (
        m, len(items), "{:,.0f}".format(tot), items[0][0], items[-1][0]))

say("")
say("3) GELOMBANG PEMBELIAN BAHAN — tanggal & nilai")
cr.execute("""
    SELECT am.date, am.name, SUM(aml.debit)
      FROM stock_move sm JOIN account_move am ON am.id=sm.account_move_id
      JOIN account_move_line aml ON aml.move_id=am.id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE sm.origin LIKE 'HPP-BOM beli%' AND aml.debit>0
     GROUP BY 1,2 ORDER BY 1""")
prev = None
for d, nm, dr in cr.fetchall():
    if d.strftime("%Y-%m") != prev:
        say("   --- %s ---" % d.strftime("%Y-%m"))
        prev = d.strftime("%Y-%m")
    say("   %s  %-26s %16s" % (d, nm, "{:,.0f}".format(dr)))

say("")
say("4) RENCANA: setoran QRIS kumulatif per tanggal vs gelombang pembelian")
cr.execute("""
    SELECT am.date, SUM(aml.debit), SUM(aml.credit)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.02'
     GROUP BY 1 ORDER BY 1""")
run = 0.0
last = None
for d, dr, cr_ in cr.fetchall():
    run += (dr or 0) - (cr_ or 0)
    if last is None or (d - last).days >= 7:
        say("   %s  saldo QRIS kumulatif = %16s" % (d, "{:,.0f}".format(run)))
        last = d
say("   AKHIR = %s" % "{:,.0f}".format(run))
say("")
say("5) BANK BSI saldo harian (semua tanggal, untuk lihat titik minus)")
cr.execute("""
    SELECT am.date, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01'
     GROUP BY 1 ORDER BY 1""")
run = 0.0
for d, bal in cr.fetchall():
    run += bal
    if run < 0:
        say("   MINUS %s  saldo=%16s" % (d, "{:,.0f}".format(run)))
say("   akhir = %16s" % "{:,.0f}".format(run))
env.cr.rollback()
