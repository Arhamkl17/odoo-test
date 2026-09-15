# -*- coding: utf-8 -*-
"""juni_juli_91b_probe_pickings.py — picking apa saja yang menempel pada sesi POS? (READ-ONLY)."""
cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
FROM, TO = "2026-06-01", "2026-09-01"

say("=" * 100)
say("A. picking ber-pos_session_id per bulan")
say("=" * 100)
cr.execute("""SELECT to_char(s.start_at,'YYYY-MM'), count(*), count(DISTINCT p.state),
                     string_agg(DISTINCT p.state, ',')
                FROM stock_picking p JOIN pos_session s ON s.id = p.pos_session_id
               WHERE s.start_at >= %s AND s.start_at < %s GROUP BY 1 ORDER BY 1""", (FROM, TO))
for bln, n, _ns, states in cr.fetchall():
    say("   %-8s picking=%-6d state=%s" % (bln, n, states))

say("")
say("   picking TANPA pos_session_id: %d" % (
    cr.execute("SELECT count(*) FROM stock_picking WHERE pos_session_id IS NULL") or cr.fetchone()[0]))

say("")
say("=" * 100)
say("B. apakah picking itu punya stock.move + valuation?")
say("=" * 100)
cr.execute("""SELECT count(DISTINCT sm.id), count(DISTINCT svl.id)
                FROM stock_picking p
                JOIN stock_move sm ON sm.picking_id = p.id
                LEFT JOIN stock_valuation_layer svl ON svl.stock_move_id = sm.id
               WHERE p.pos_session_id IS NOT NULL""")
a, b = cr.fetchone()
say("   stock.move dari picking POS = %s | valuation layer = %s" % (a, b))

cr.execute("""SELECT count(*) FROM account_move am
               WHERE am.ref LIKE %s OR am.ref LIKE %s""", ("%picking%", "%POS%"))
say("   account_move ref menyebut picking/POS = %s" % cr.fetchone()[0])

say("")
say("=" * 100)
say("C. contoh picking POS (5 pertama)")
say("=" * 100)
cr.execute("""SELECT p.id, p.name, p.origin, p.state, p.date, p.pos_session_id,
                     s.config_id, to_char(p.date,'YYYY-MM')
                FROM stock_picking p LEFT JOIN pos_session s ON s.id=p.pos_session_id
               WHERE p.pos_session_id IS NOT NULL ORDER BY p.id LIMIT 5""")
for r in cr.fetchall():
    say("   id=%-6s %-16s origin=%-14s state=%-10s date=%s sesi=%s cfg=%s" % (
        r[0], r[1], (r[2] or "")[:14], r[3], r[4], r[5], r[6]))

say("")
say("=" * 100)
say("D. REKAP semua stock.move menurut origin (top 15)")
say("=" * 100)
cr.execute("""SELECT COALESCE(NULLIF(split_part(origin,' ',1),''),'(kosong)') o,
                     count(*), count(DISTINCT picking_id)
                FROM stock_move GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
for o, n, np in cr.fetchall():
    say("   %-40s move=%-7d picking=%d" % (o[:40], n, np))

say("")
say("=" * 100)
say("E. JE 'Modal kerja' / 'Setoran QRIS' / 'Settlement' — nama ref persisnya")
say("=" * 100)
cr.execute("""SELECT DISTINCT ref FROM account_move
               WHERE (ref ILIKE '%Modal kerja%' OR ref ILIKE '%Setoran QRIS%'
                      OR ref ILIKE '%Settlement%' OR ref ILIKE '%e-wallet%')
                 AND date >= %s AND date < %s ORDER BY 1""", (FROM, TO))
for (r,) in cr.fetchall():
    say("   %s" % r)

env.cr.rollback()
