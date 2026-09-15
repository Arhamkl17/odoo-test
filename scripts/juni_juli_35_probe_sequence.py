# -*- coding: utf-8 -*-
"""READ-ONLY: kenapa sequence MISC memilih 0001 padahal sudah ada 0001/0002?"""
cr = env.cr
say = lambda m="": print(m)

say("=" * 100)
say("1) NAMA JE JURNAL MISC per bulan")
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, COUNT(*), MIN(am.name), MAX(am.name)
      FROM account_move am WHERE am.journal_id=3
     GROUP BY 1 ORDER BY 1""")
for m, n, mn, mx in cr.fetchall():
    say("   %s n=%-4d min=%-24s max=%-24s" % (m, n, mn, mx))

say("")
say("2) BEBERAPA CONTOH NAMA MISC Juni")
cr.execute("""SELECT id, name, date, state, ref FROM account_move
               WHERE journal_id=3 AND date>='2026-06-01' AND date<'2026-07-01'
               ORDER BY name""")
for i, nm, d, st, ref in cr.fetchall():
    say("   id=%-6s %-26s %s %-8s %s" % (i, nm, d, st, (ref or "")[:44]))

say("")
say("3) STRUKTUR SEQUENCE (ir.sequence) untuk jurnal ini")
cr.execute("""SELECT id, name, code, prefix, suffix, padding, number_next, number_next_actual,
                     implementation, use_date_range
                FROM ir_sequence ORDER BY id""")
for r in cr.fetchall():
    say("   seq id=%-4s code=%-34s prefix=%-14s pad=%-3s next=%-6s date_range=%s" % (
        r[0], (r[2] or "")[:34], (r[3] or "")[:14], r[5], r[7], r[9]))

say("")
say("4) DATE RANGE SEQUENCE")
try:
    cr.execute("SELECT id, sequence_id, date_from, date_to, number_next_actual FROM ir_sequence_date_range ORDER BY id DESC LIMIT 20")
    for r in cr.fetchall():
        say("   range id=%-4s seq=%-4s %s..%s next=%s" % r)
except Exception as e:
    say("   ERR %r" % e)

say("")
say("5) FIELD sequence pada account.move (mekanisme Odoo 19)")
cr.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='account_move' AND column_name LIKE '%sequen%'""")
for r in cr.fetchall():
    say("   kolom %s" % r[0])
try:
    cr.execute("""SELECT id, name, journal_id, sequence_prefix, sequence_number
                    FROM account_move WHERE journal_id=3 AND date>='2026-06-01'
                   ORDER BY date LIMIT 8""")
    for r in cr.fetchall():
        say("   id=%-6s %-26s seq_prefix=%-16s seq_no=%s" % r)
except Exception as e:
    say("   ERR %r" % e)
env.cr.rollback()
