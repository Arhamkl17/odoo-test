# -*- coding: utf-8 -*-
"""
juni_juli_76_probe_segepok.py — apakah harga PAKET keluarga SEGEPOK masuk akal? (READ-ONLY)

Kecurigaan: SEGEPOK BERLIMA (5 orang) dijual 61.777 sementara AYAM SEGEPOK SINGLE
(1 orang) 69.000 -- paket 5 porsi lebih murah dari 1 porsi.

  su odoo ... < scripts/juni_juli_76_probe_segepok.py
"""
from collections import Counter

Prod = env["product.product"]
Bom = env["mrp.bom"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

cr = env.cr
cr.execute("""
    SELECT pt.id, pt.name->>'en_US', pt.list_price
      FROM product_template pt
     WHERE pt.id IN (
        SELECT product_tmpl_id FROM mrp_bom)
       AND (pt.name->>'en_US' ILIKE '%SEGEPOK%' OR pt.name->>'en_US' ILIKE '%BEREMPAT%')
     ORDER BY pt.list_price DESC""")
tmpls = cr.fetchall()

say("=" * 110)
say("KELUARGA SEGEPOK — harga jual vs isi resep")
say("=" * 110)
for tid, nm, price in tmpls:
    bom = Bom.search([("product_tmpl_id", "=", tid)], limit=1)
    say("")
    say("%-46s harga %10s | BOM %s" % ((nm or "")[:46], money(price),
                                       len(bom.bom_line_ids) if bom else "-"))
    if not bom:
        continue
    garis = []
    for l in bom.bom_line_ids:
        garis.append((l.product_id.display_name, l.product_qty,
                      l.product_id.product_tmpl_id.list_price))
    for g in sorted(garis, key=lambda x: -x[2] * x[1])[:12]:
        say("       %-44s x%-8s harga jual %8s" % (g[0][:44], ("%.2f" % g[1]).rstrip("0").rstrip("."),
                                                   money(g[2])))
    say("       total %d baris" % len(garis))

say("")
say("=" * 110)
say("PENJUALAN keluarga SEGEPOK (Juni-Agustus)")
say("=" * 110)
cr.execute("""
    SELECT pt.name->>'en_US', SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol
      JOIN pos_order po ON po.id = pol.order_id
      JOIN product_product pp ON pp.id = pol.product_id
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
       AND (pt.name->>'en_US' ILIKE '%SEGEPOK%' OR pt.name->>'en_US' ILIKE '%BEREMPAT%')
     GROUP BY 1 ORDER BY 3 DESC""")
for nm, q, rev in cr.fetchall():
    say("   %-46s qty %8s omzet %14s  rata2 %10s" % (
        (nm or "")[:46], money(q), money(rev), money(float(rev) / float(q) if q else 0)))

env.cr.rollback()
