# -*- coding: utf-8 -*-
"""juni_juli_15_probe_cash2.py — lacak move pembawa 'Perbedaan kas' Juli (READ-ONLY)."""
cr = env.cr
AM = env["account.move"]
Sess = env["pos.session"]
say = lambda m="": print(m)

say("=" * 104)
say("A. MOVE yang punya baris 6101.23 'Perbedaan kas' — 6 pertama Juli")
cr.execute("""
    SELECT am.id, am.name, am.date, am.ref, aj.code, am.state,
           SUM(aml.debit), SUM(aml.credit), COUNT(aml.id)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_journal aj ON aj.id = am.journal_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE aa.code_store->>'1' = '6101.23' AND aml.name ILIKE 'Perbedaan kas%%'
       AND am.date >= '2026-07-01' AND am.date < '2026-08-01'
     GROUP BY am.id, am.name, am.date, am.ref, aj.code, am.state
     ORDER BY am.id LIMIT 6""")
rows = cr.fetchall()
say("%-8s %-22s %-12s %-14s %-6s %-9s %16s" % ("id", "name", "date", "journal", "state", "ref", "debit"))
for r in rows:
    say("%-8s %-22s %-12s %-14s %-6s %-9s %16s" % (
        r[0], r[1], r[2], r[4], r[5], (r[3] or "")[:14], "{:,.2f}".format(r[6] or 0)))

if rows:
    mid = rows[0][0]
    m = AM.browse(mid)
    say("")
    say("B. Isi lengkap move id=%s (%s / %s / %s)  session=%s" % (
        mid, m.name, m.ref, m.date, m.pos_session_ids.ids if "pos_session_ids" in m._fields else "-"))
    for l in m.line_ids:
        say("   %-14s %-46s D%16s K%16s  [%s]" % (
            l.account_id.code, (l.name or "")[:46],
            "{:,.2f}".format(l.debit), "{:,.2f}".format(l.credit), (l.ref or "")[:16]))

say("")
say("C. Sesi Juli: bandingkan 'end' vs 'end_real' vs diff (10 pertama)")
for s in Sess.search([("start_at", ">=", "2026-07-01"), ("start_at", "<", "2026-08-01")],
                     order="start_at", limit=10):
    mv = s.move_id
    say("   sesi %-5s %-22s %s | end=%14s end_real=%14s diff=%14s | move=%s %s" % (
        s.id, s.config_id.name, str(s.start_at)[:10],
        "{:,.0f}".format(s.cash_register_balance_end or 0),
        "{:,.0f}".format(s.cash_register_balance_end_real or 0),
        "{:,.0f}".format(s.cash_register_difference or 0),
        mv.name or "-", mv.date or "-"))

say("")
say("D. Berapa sesi Juni/Juli yang PUNYA baris 'Perbedaan kas' non-nol?")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM'), COUNT(DISTINCT am.id), SUM(aml.debit)
      FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
      JOIN account_account aa ON aa.id = aml.account_id
     WHERE aa.code_store->>'1' = '6101.23' AND aml.name ILIKE 'Perbedaan kas%%'
       AND aml.debit > 0.01 AND am.date >= '2026-06-01' AND am.date < '2026-10-01'
     GROUP BY 1 ORDER BY 1""")
for bln, n, d in cr.fetchall():
    say("   %s  move=%d  total=%18s" % (bln, n, "{:,.2f}".format(d or 0)))
say("=" * 104)
env.cr.rollback()
