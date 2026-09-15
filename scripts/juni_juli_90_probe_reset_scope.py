# -*- coding: utf-8 -*-
"""
juni_juli_90_probe_reset_scope.py — apa saja yang menempel pada sesi POS Jun-Agu? (READ-ONLY)

Tujuan: memastikan reset POS tidak ikut membuang data yang TIDAK boleh hilang
(catering B2B Agustus, HPP BTL, pembelian bahan).

  su odoo ... < scripts/juni_juli_90_probe_reset_scope.py
"""
cr = env.cr
Sess = env["pos.session"]
POSo = env["pos.order"]
AM = env["account.move"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
FROM, TO = "2026-06-01", "2026-09-01"

sess = Sess.search([("start_at", ">=", FROM), ("start_at", "<", TO)])
orders = POSo.search([("date_order", ">=", FROM), ("date_order", "<", TO)])
say("=" * 108)
say("SESI & ORDER Jun-Agu")
say("=" * 108)
say("sesi  : %d" % len(sess))
say("order : %d   omzet %s" % (len(orders), money(sum(orders.mapped("amount_total")))))
cr.execute("""SELECT to_char(po.date_order,'YYYY-MM'), count(*), sum(po.amount_total)
                FROM pos_order po WHERE po.date_order >= %s AND po.date_order < %s
               GROUP BY 1 ORDER BY 1""", (FROM, TO))
for bln, n, rev in cr.fetchall():
    say("   %-8s %5d order  %16s" % (bln, n, money(rev)))

say("")
say("=" * 108)
say("A. apakah order POS punya PICKING / STOCK MOVE? (menerangkan HPP ikut atau tidak)")
say("=" * 108)
cr.execute("""SELECT count(*) FROM stock_picking WHERE origin LIKE 'POS%'
                AND create_date >= '2026-06-01'""")
say("picking origin POS%% (semua waktu)      : %s" % cr.fetchone()[0])
cr.execute("""SELECT count(*) FROM stock_move
               WHERE origin LIKE '%POS%' OR reference LIKE '%POS%'""")
say("stock.move yang menyebut POS           : %s" % cr.fetchone()[0])
cr.execute("""SELECT origin, count(*) FROM stock_move
               WHERE create_date >= '2026-08-01'
               GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")
say("asmove terbaru (Agustus ke atas) per origin:")
for o, n in cr.fetchall():
    say("      %-52s %d" % ((o or "(kosong)")[:52], n))

say("")
say("=" * 108)
say("B. JE yang menempel pada sesi (akan dihapus)")
say("=" * 108)
cr.execute("""SELECT am.ref, count(*), sum(am.amount_total)
                FROM pos_session s JOIN account_move am ON am.id = s.move_id
               WHERE s.start_at >= %s AND s.start_at < %s
               GROUP BY 1 ORDER BY 2 DESC LIMIT 6""", (FROM, TO))
for r, n, v in cr.fetchall():
    say("   %-52s %4d  %s" % ((r or "")[:52], n, money(v)))
cr.execute("""SELECT am.ref, count(*), sum(am.amount_total) FROM account_move am
               WHERE am.ref LIKE 'Settlement%' AND am.date >= %s AND am.date < %s
               GROUP BY 1 ORDER BY 2 DESC""", (FROM, TO))
for r, n, v in cr.fetchall():
    say("   %-52s %4d  %s" % ((r or "")[:52], n, money(v)))

say("")
say("=" * 108)
say("C. YANG TIDAK BOLEH HILANG — invoice B2B / catering")
say("=" * 108)
B2B = AM.search([("move_type", "=", "out_invoice"), ("date", ">=", FROM), ("date", "<", TO)])
for m in B2B:
    say("   %-22s %-12s %-30s %12s  state=%s" % (
        m.name, str(m.invoice_date), (m.partner_id.name or "")[:30],
        money(m.amount_total), m.state))
say("   total %d invoice" % len(B2B))

say("")
say("=" * 108)
say("D. stock move HPP (origin HPP-BOM) — TIDAK disentuh reset POS")
say("=" * 108)
cr.execute("""SELECT split_part(origin,' ',2), count(*), count(DISTINCT stock_move_id)
                FROM stock_valuation_layer svl JOIN stock_move sm ON sm.id = svl.stock_move_id
               WHERE sm.origin LIKE 'HPP-BOM%' GROUP BY 1""")
try:
    for bln, n, m in cr.fetchall():
        say("   %-12s svl=%-5d move=%d" % (bln, n, m))
except Exception as e:
    say("   (gagal via svl: %s)" % repr(e)[:90])
cr.execute("""SELECT split_part(origin,' ',-1), count(*) FROM stock_move
               WHERE origin LIKE 'HPP-BOM%' GROUP BY 1 ORDER BY 1""")
for bln, n in cr.fetchall():
    say("   origin HPP-BOM ... %-14s %d move" % (bln, n))

say("")
say("=" * 108)
say("E. SESSION POS yang masih OPEN (kalau ada, reset akan menolak)")
say("=" * 108)
op = Sess.search([("state", "!=", "closed"), ("start_at", ">=", FROM), ("start_at", "<", TO)])
say("   %d sesi belum closed %s" % (len(op), op.mapped("name")))

env.cr.rollback()
