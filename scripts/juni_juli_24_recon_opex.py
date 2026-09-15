# -*- coding: utf-8 -*-
"""juni_juli_24_recon_opex.py — bedah beban operasional & sisa HPP Agustus (READ-ONLY)."""
cr = env.cr
say = lambda m="": print(m)

say("=" * 106)
say("A. BEBAN OPERASIONAL AGUSTUS — per akun")
cr.execute("""
    SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'),
           COUNT(*), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.account_type IN ('expense','expense_depreciation')
     GROUP BY 1,2 HAVING ABS(SUM(aml.balance)) > 0.01 ORDER BY 4 DESC""")
tot = 0.0
for kode, nama, n, bal in cr.fetchall():
    tot += bal
    say("   %-10s %-44s n=%-4d %16s" % (kode, (nama or "")[:44], n, "{:,.2f}".format(bal)))
say("   %-10s %-44s     %16s" % ("", "TOTAL BEBAN", "{:,.2f}".format(tot)))

say("")
say("B. JE BEBAN AGUSTUS — dokumen per pos (untuk direkalibrasi)")
cr.execute("""
    SELECT aa.code_store->>'1', am.name, aj.code, am.date, am.ref,
           SUM(aml.balance), COUNT(*)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
      JOIN account_journal aj ON aj.id = am.journal_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.code_store->>'1' IN ('6101.03','6101.11','6101.06','6300.01','6101.20','6101.21','6101.22')
     GROUP BY 1,2,3,4,5 ORDER BY 1,6 DESC""")
for kode, nm, jr, dt, ref, bal, n in cr.fetchall():
    say("   %-9s %-20s %-6s %-12s %16s  ref=%s" % (
        kode, nm or "", jr, dt, "{:,.2f}".format(bal), (ref or "")[:40]))

say("")
say("C. PENYUSUTAN (6200.*, 6101.14/16/17)")
cr.execute("""
    SELECT aa.code_store->>'1', COALESCE(aa.name->>'en_US', aa.name->>'1'), COUNT(*), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND aa.account_type = 'expense_depreciation'
     GROUP BY 1,2 ORDER BY 1""")
for kode, nama, n, bal in cr.fetchall():
    say("   %-10s %-48s n=%-4d %16s" % (kode, (nama or "")[:48], n, "{:,.2f}".format(bal)))

say("")
say("D. SISA HPP AGUSTUS dari sumber NON-konsumsi-BOM (perlu dinilai ulang)")
cr.execute("""
    SELECT aa.code_store->>'1', aj.code, COUNT(*), SUM(aml.balance),
           string_agg(DISTINCT LEFT(COALESCE(am.ref,'-'), 30), ' | ')
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
      JOIN account_journal aj ON aj.id = am.journal_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.account_type = 'expense_direct_cost' AND am.origin != 'HPP-BOM'
       AND NOT (am.ref ILIKE 'HPP-BOM%')
     GROUP BY 1,2 HAVING ABS(SUM(aml.balance)) > 0.01 ORDER BY 4 DESC""")
for kode, jr, n, bal, refs in cr.fetchall():
    say("   %-9s %-6s n=%-4d %16s  %s" % (kode, jr, n, "{:,.2f}".format(bal), (refs or "")[:44]))

say("")
say("E. HPP AGUSTUS menurut asal (BOM vs lainnya)")
cr.execute("""
    SELECT CASE WHEN aml.name ILIKE 'HPP-BOM%' THEN 'konsumsi BOM (P7)' ELSE 'lainnya' END asal,
           COUNT(*), SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND aa.account_type = 'expense_direct_cost'
     GROUP BY 1 ORDER BY 3 DESC""")
for asal, n, bal in cr.fetchall():
    say("   %-22s n=%-5d %18s" % (asal, n, "{:,.2f}".format(bal or 0)))

say("")
say("F. Pembayaran gaji Agustus (74 jt di bank?) — isi JE-nya")
cr.execute("""
    SELECT am.name, aj.code, am.date, am.ref, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_journal aj ON aj.id = am.journal_id
     WHERE am.state='posted' AND am.date >= '2026-08-01' AND am.date < '2026-09-01'
       AND (am.ref ILIKE '%gaji%' OR am.name IN (SELECT am2.name FROM account_move am2
            JOIN account_move_line l ON l.move_id=am2.id JOIN account_account a ON a.id=l.account_id
            WHERE a.code_store->>'1'='6101.03'))
     GROUP BY 1,2,3,4""")
for nm, jr, dt, ref, bal in cr.fetchall():
    say("   %-22s %-6s %-12s %16s  ref=%s" % (nm or "", jr, dt, "{:,.2f}".format(bal or 0), (ref or "")[:44]))
say("=" * 106)
env.cr.rollback()
