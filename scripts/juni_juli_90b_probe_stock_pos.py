# -*- coding: utf-8 -*-
"""juni_juli_90b_probe_stock_pos.py — apakah sesi POS melahirkan stock move? (READ-ONLY)."""
cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
FROM, TO = "2026-06-01", "2026-09-01"

say("=" * 100)
say("A. stock.move yang LAHIR dari POS (kolom yang mengarah ke pos_order / picking)")
say("=" * 100)
cr.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='stock_move' AND column_name ILIKE '%pos%'""")
say("kolom bertema pos di stock_move: %s" % [r[0] for r in cr.fetchall()])
cr.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='stock_picking' AND column_name ILIKE '%pos%'""")
say("kolom bertema pos di stock_picking: %s" % [r[0] for r in cr.fetchall()])

say("")
cr.execute("""SELECT count(*) FROM stock_move WHERE origin LIKE 'POS%%'""")
say("stock.move origin LIKE 'POS%%'                : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM stock_move WHERE reference LIKE 'POS%%'""")
say("stock.move reference LIKE 'POS%%'             : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM stock_picking""")
say("total stock.picking                            : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM stock_move WHERE origin LIKE 'HPP-BOM%%'""")
say("stock.move origin HPP-BOM%%                    : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM stock_move""")
say("total stock.move                               : %s" % cr.fetchone()[0])

say("")
say("=" * 100)
say("B. JE settlement pada rentang Jun-Agu")
say("=" * 100)
cr.execute("""SELECT am.ref, count(*), sum(abs(am.amount_total))
                FROM account_move am
               WHERE am.ref LIKE %s AND am.date >= %s AND am.date < %s
               GROUP BY 1 ORDER BY 2 DESC""", ("Settlement%", FROM, TO))
for r, n, v in cr.fetchall():
    say("   %-56s %4d  %s" % ((r or "")[:56], n, money(v)))

say("")
say("=" * 100)
say("C. JE sesi per bulan (yang akan dihapus)")
say("=" * 100)
cr.execute("""SELECT to_char(s.start_at,'YYYY-MM'), count(*), count(am.id)
                FROM pos_session s LEFT JOIN account_move am ON am.id = s.move_id
               WHERE s.start_at >= %s AND s.start_at < %s GROUP BY 1 ORDER BY 1""", (FROM, TO))
for bln, ns, nm in cr.fetchall():
    say("   %-8s sesi=%-5d punya JE=%d" % (bln, ns, nm))

say("")
say("=" * 100)
say("D. invoice B2B (TIDAK BOLEH HILANG)")
say("=" * 100)
cr.execute("""SELECT am.name, am.invoice_date, rp.name, am.amount_total, am.state
                FROM account_move am LEFT JOIN res_partner rp ON rp.id = am.partner_id
               WHERE am.move_type='out_invoice' AND am.date >= %s AND am.date < %s
               ORDER BY am.date""", (FROM, TO))
for nm, dt, pt, tot, st in cr.fetchall():
    say("   %-22s %-12s %-28s %14s  %s" % (nm, str(dt), (pt or "")[:28], money(tot), st))

say("")
say("=" * 100)
say("E. sesi belum closed")
say("=" * 100)
Sess = env["pos.session"]
op = Sess.search([("state", "!=", "closed"), ("start_at", ">=", FROM), ("start_at", "<", TO)])
say("   %d %s" % (len(op), op.mapped("name")))

env.cr.rollback()
