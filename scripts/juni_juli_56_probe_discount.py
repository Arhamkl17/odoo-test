# -*- coding: utf-8 -*-
"""juni_juli_56_probe_discount.py — dari mana harga efektif murah itu (READ-ONLY)."""
cr = env.cr
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))

TARGETS = ["PKG LOKAL DUO", "PAKET GEPREK BAKAR", "SEGEPOK BERLIMA",
           "GEPREK ORIGINAL SAYAP", "YUKSSS RAMA 1", "MOZZARELLA"]

for tx in TARGETS:
    p = Prod.search([("display_name", "=", tx)], limit=1)
    if not p:
        say("[%s] tidak ada" % tx)
        continue
    say("=" * 100)
    say("%s  id=%s  list_price(tmpl)=%s  lst_price(prod)=%s" % (
        tx, p.id, money(p.product_tmpl_id.list_price), money(p.lst_price)))
    cr.execute("""
        SELECT pol.price_unit, COUNT(*), SUM(pol.qty), SUM(pol.price_subtotal),
               COUNT(DISTINCT po.id)
          FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
         WHERE pol.product_id=%s AND po.state IN ('paid','done','invoiced')
           AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
         GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", (p.id,))
    say("   %-12s %6s %8s %16s %7s" % ("price_unit", "baris", "qty", "subtotal", "order"))
    for pu, n, q, st, no in cr.fetchall():
        say("   %-12s %6d %8.0f %16s %7d" % (money(pu), n, float(q or 0), money(st), no))
    cr.execute("""SELECT COUNT(*) FROM pos_order_line WHERE product_id=%s""", (p.id,))
    say("   total baris sepanjang waktu: %s" % cr.fetchone()[0])

say("")
say("=" * 100)
say("Apakah ada pricelist / diskon tersimpan di baris POS?")
cr.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='pos_order_line' AND column_name LIKE '%%discount%%'""")
say("   kolom discount di pos_order_line: %s" % [r[0] for r in cr.fetchall()])
cr.execute("""SELECT COALESCE(SUM(discount),0), COUNT(*) FROM pos_order_line WHERE discount > 0""")
say("   baris dengan discount>0: %s" % (cr.fetchone(),))
cr.execute("""SELECT COALESCE(SUM(pol.discount),0), COUNT(*), MIN(pol.price_unit), MAX(pol.price_unit)
                FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
               WHERE po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'""")
say("   Juni-Agu: %s" % (cr.fetchone(),))
cr.execute("""SELECT id, name FROM product_pricelist ORDER BY id LIMIT 10""")
say("   pricelist: %s" % cr.fetchall())
env.cr.rollback()
