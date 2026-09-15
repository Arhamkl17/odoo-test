# -*- coding: utf-8 -*-
"""READ-ONLY: kronologi kas Juni + uji apakah stock.move done boleh diubah tanggalnya."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 100)
say("1) JE BESAR 1 JUNI (modal & aset tetap)")
cr.execute("""
    SELECT am.date, am.name, aa.code_store->>'1', aa.name->>'en_US', aml.debit, aml.credit
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND am.date>='2026-06-01' AND am.date<='2026-06-05'
       AND (aa.code_store->>'1' LIKE '3%' OR aa.account_type='asset_fixed' OR aa.code_store->>'1'='1101.01')
     ORDER BY am.date, am.id""")
for d, nm, code, acct, dr, cr_ in cr.fetchall():
    say("   %s  %-22s %-10s %-32s dr=%14s cr=%14s" % (
        d, nm, code, (acct or "")[:32], "{:,.0f}".format(dr), "{:,.0f}".format(cr_)))

say("")
say("2) SALDO BANK HARIAN JUNI (dengan pembelian 1 Juni DIKELUARKAN = simulasi pindah ke akhir bulan)")
cr.execute("""
    SELECT am.date, aml.balance, aa.code_store->>'1' code, am.name
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01' AND am.date<'2026-07-01'
     ORDER BY am.date, am.id""")
by_date = {}
for d, bal, code, nm in cr.fetchall():
    by_date.setdefault(d, 0.0)
    by_date[d] += bal
run = 0.0
for d in sorted(by_date):
    run += by_date[d]
    say("   %s  mutasi=%16s  saldo=%16s" % (d, "{:,.0f}".format(by_date[d]), "{:,.0f}".format(run)))

say("")
say("3) UJI: apakah stock.move berstatus done boleh diubah tanggal/quant-nya?")
cr.execute("""SELECT id, reference, date, quantity, state FROM stock_move
               WHERE origin LIKE 'HPP-BOM beli%%' ORDER BY id LIMIT 3""")
try:
    rows = cr.fetchall()
    for r in rows:
        say("   move id=%s ref=%s date=%s qty=%s state=%s" % r)
except Exception as e:
    say("   ERR %r" % e)
say("   (uji tulis dilakukan terpisah dengan RUN=1 — sekarang hanya lihat struktur)")
try:
    MV = env["stock.move"].browse(rows[0][0])
    say("   picked=%s | is_inventory=%s | account_move_id=%s" % (
        MV.picked, MV.is_inventory, MV.account_move_id.id if MV.account_move_id else None))
except Exception as e:
    say("   ERR browse %r" % e)

say("")
say("4) TRANSAKSI BANK JUNI menurut AKUN LAWAN (ke mana uang pergi)")
cr.execute("""
    SELECT am.date, am.name, aa.code_store->>'1', aa.name->>'en_US', aml.debit, aml.credit
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.code_store->>'1'='1101.01' AND am.date<'2026-07-01'
     ORDER BY am.date, am.id LIMIT 60""")
for d, nm, code, acct, dr, cr_ in cr.fetchall():
    say("   %s %-24s %-10s %-28s dr=%14s cr=%14s" % (
        d, nm[:24], code, (acct or "")[:28], "{:,.0f}".format(dr), "{:,.0f}".format(cr_)))
env.cr.rollback()
