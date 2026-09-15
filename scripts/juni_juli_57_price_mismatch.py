# -*- coding: utf-8 -*-
"""juni_juli_57_price_mismatch.py — daftar harga POS != harga master (READ-ONLY)."""
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr.execute("""
    SELECT pol.product_id,
           COUNT(*) baris,
           COUNT(DISTINCT pol.price_unit) n_harga,
           MIN(pol.price_unit), MAX(pol.price_unit),
           SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
rows = cr.fetchall()
say("=" * 130)
say("HARGA POS != HARGA MASTER  (Juni-Agustus 2026)")
say("=" * 130)
say("%-50s %8s %9s %7s %6s %10s %13s" % (
    "produk", "master", "min POS", "maksPOS", "nhrg", "qty", "omzet"))
say("-" * 130)
bad = nostale = 0
tot_gap = 0.0
for pid, nbar, nh, mn, mx, qty, rev in rows:
    p = Prod.browse(int(pid)) if pid else None
    if not p or not p.exists():
        continue
    master = p.product_tmpl_id.list_price or 0.0
    mn, mx, qty, rev = float(mn or 0), float(mx or 0), float(qty or 0), float(rev or 0)
    if master <= 0:
        continue
    if abs(mn - master) < 0.01 and abs(mx - master) < 0.01:
        nostale += 1
        continue
    bad += 1
    tot_gap += qty * (master - rev / qty if qty else 0)
    say("%-50s %8s %9s %7s %6d %10.0f %13s" % (
        (p.display_name or "")[:50], money(master), money(mn), money(mx), nh, qty, money(rev)))
say("-" * 130)
say("produk dengan harga POS != master : %d" % bad)
say("produk yang harganya sudah selaras : %d" % nostale)
say("potensi selisih omzet bila semua dijual di harga master: %s" % money(tot_gap))
env.cr.rollback()
