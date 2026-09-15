# -*- coding: utf-8 -*-
"""READ-ONLY: struktur ir_sequence + state sequence jurnal MISC."""
cr = env.cr
say = lambda m="": print(m)

for tbl in ("ir_sequence", "ir_sequence_date_range"):
    cr.execute("""SELECT column_name, data_type FROM information_schema.columns
                   WHERE table_name=%s ORDER BY ordinal_position""", (tbl,))
    say("KOLOM %s: %s" % (tbl, ", ".join("%s(%s)" % (c, t) for c, t in cr.fetchall())))
    say("")

say("=" * 100)
say("ACCOUNT.JOURNAL yang ada (cari yang punya sequence naming)")
cr.execute("""SELECT id, code, name->>'en_US', type FROM account_journal ORDER BY id""")
for i, code, nm, t in cr.fetchall():
    say("   id=%-4s %-10s %-38s %s" % (i, code, (nm or "")[:38], t))

say("")
say("SEQUENCE yang terkait jurnal (via ir_sequence.code = 'account.move.<journal_id>')")
cr.execute("SELECT id, code, prefix, padding, number_next FROM ir_sequence ORDER BY id")
segs = cr.fetchall()
for i, code, prefix, pad, nxt in segs:
    say("   id=%-4s code=%-30s prefix=%-18s pad=%-3s next_awal=%s" % (i, (code or "")[:30], (prefix or "")[:18], pad, nxt))

say("")
say("DATE RANGE (kalau ada)")
try:
    cr.execute("SELECT id, sequence_id, date_from, date_to, number_next FROM ir_sequence_date_range ORDER BY id")
    for r in cr.fetchall():
        say("   range id=%-5s seq=%-5s %s..%s next=%s" % r)
except Exception as e:
    say("   ERR %r" % e)
    env.cr.rollback()

say("")
say("ACCOUNT.MOVE: kolom sequence_* + isi untuk jurnal 3")
cr.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='account_move' AND column_name LIKE '%sequen%' OR table_name='account_move' AND column_name='name'""")
cols = [r[0] for r in cr.fetchall()]
say("   kolom: %s" % ", ".join(cols))
cr.execute("""SELECT id, name, sequence_prefix, sequence_number FROM account_move
               WHERE journal_id=3 ORDER BY sequence_number DESC LIMIT 6""")
for r in cr.fetchall():
    say("   id=%-6s %-26s prefix=%-16s no=%s" % r)

say("")
say("NAMA TERPAKAI per prefix (untuk hitung nomor aman)")
cr.execute("""SELECT sequence_prefix, MAX(sequence_number) FROM account_move
               WHERE sequence_prefix IS NOT NULL GROUP BY 1 ORDER BY 1""")
for p, mx in cr.fetchall():
    say("   %-18s max_no=%s" % (p, mx))
env.cr.rollback()
