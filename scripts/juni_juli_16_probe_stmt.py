# -*- coding: utf-8 -*-
"""juni_juli_16_probe_stmt.py — isi account.bank.statement sesi kas (READ-ONLY)."""
cr = env.cr
St = env["account.bank.statement"]
Sess = env["pos.session"]
say = lambda m="": print(m)

say("=" * 110)
for tag, sid in (("JULI  sesi 511 (Pallangga 2026-07-01)", 511),
                 ("AGUSTUS sesi 202 (Pallangga 2026-08-01)", 202)):
    s = Sess.browse(sid)
    say("%s | config=%s | cash_control=%s" % (tag, s.config_id.name, s.config_id.cash_control))
    say("   sesi: start=%s end=%s end_real=%s diff=%s" % (
        "{:,.2f}".format(s.cash_register_balance_start or 0),
        "{:,.2f}".format(s.cash_register_balance_end or 0),
        "{:,.2f}".format(s.cash_register_balance_end_real or 0),
        "{:,.2f}".format(s.cash_register_difference or 0)))
    sts = St.search([("line_ids.pos_session_id", "=", sid)])
    say("   statement: %d" % len(sts))
    for st in sts:
        say("      id=%-5s jurnal=%-6s tanggal=%-12s start=%-16s end_real=%-16s total_entry=%s" % (
            st.id, st.journal_id.code, st.date,
            "{:,.2f}".format(st.balance_start or 0),
            "{:,.2f}".format(st.balance_end_real or 0),
            "{:,.2f}".format(sum(st.line_ids.mapped("amount")))))
        for l in st.line_ids:
            say("         line id=%-6s amount=%-16s payment_ref=%s" % (
                l.id, "{:,.2f}".format(l.amount or 0), l.payment_ref))
    say("")

say("=" * 110)
say("Statement line pada jurnal kas (CSH2/CSHB) untuk Juli — 8 pertama, via SQL")
cr.execute("""
    SELECT absl.id, absl.date, absl.amount, absl.payment_ref, absl.pos_session_id,
           absl.move_id, aj.code
      FROM account_bank_statement_line absl JOIN account_journal aj ON aj.id = absl.journal_id
     WHERE aj.code IN ('CSH2','CSHB') AND absl.date >= '2026-07-01' AND absl.date < '2026-07-05'
     ORDER BY absl.id LIMIT 12""")
for r in cr.fetchall():
    say("   id=%-6s %-12s amount=%-16s sess=%-6s move=%-8s jr=%-5s ref=%s" % (
        r[0], r[1], "{:,.2f}".format(r[2] or 0), r[4], r[5], r[6], (r[3] or "")[:30]))

say("")
say("Jumlah baris statement kas per bulan + kolom pos_session_id terisi?")
cr.execute("""
    SELECT to_char(absl.date,'YYYY-MM'), aj.code, COUNT(*), COUNT(absl.pos_session_id),
           SUM(absl.amount)
      FROM account_bank_statement_line absl JOIN account_journal aj ON aj.id = absl.journal_id
     WHERE aj.code IN ('CSH2','CSHB') AND absl.date >= '2026-06-01' AND absl.date < '2026-10-01'
     GROUP BY 1,2 ORDER BY 1,2""")
for bln, jr, n, n_sess, amt in cr.fetchall():
    say("   %s %-6s baris=%-5d punya_sesi=%-5d total=%18s" % (
        bln, jr, n, n_sess, "{:,.2f}".format(amt or 0)))
say("=" * 110)
env.cr.rollback()
