# -*- coding: utf-8 -*-
"""READ-ONLY: state date-range sequence jurnal MISC."""
cr = env.cr
say = lambda m="": print(m)

J = env["account.journal"].browse(3)
say("=" * 100)
say("JURNAL MISC: sequence_id=%s (%s)" % (J.sequence_id.id, J.sequence_id.display_name))
say("   prefix=%r padding=%s use_date_range=%s implementation=%s" % (
    J.sequence_id.prefix, J.sequence_id.padding, J.sequence_id.use_date_range,
    J.sequence_id.implementation))
say("")
say("DATE RANGE milik sequence ini:")
cr.execute("""SELECT id, date_from, date_to, number_next_actual
                FROM ir_sequence_date_range WHERE sequence_id=%s ORDER BY date_from""",
           (J.sequence_id.id,))
for i, df, dt, nn in cr.fetchall():
    say("   range id=%-4s %s .. %s   number_next_actual=%s" % (i, df, dt, nn))

say("")
say("UJI: _get_last_sequence() untuk move Juni, Juli, Agustus")
for d in ("2026-06-01", "2026-07-01", "2026-08-31"):
    m = env["account.move"].new({"journal_id": 3, "date": d, "move_type": "entry"})
    try:
        say("   tgl %s -> _get_last_sequence() = %r | _get_starting_sequence() = %r" % (
            d, m._get_last_sequence(), m._get_starting_sequence()))
    except Exception as e:
        say("   tgl %s -> ERR %r" % (d, e))

say("")
say("NAMA TERAKHIR per bulan di jurnal ini (berdasarkan sequence_number)")
cr.execute("""SELECT to_char(date,'YYYY-MM') m, MAX(sequence_number) FROM account_move
               WHERE journal_id=3 AND name<>'/' GROUP BY 1 ORDER BY 1""")
for m, mx in cr.fetchall():
    say("   %s max_seq_no=%s" % (m, mx))
env.cr.rollback()
