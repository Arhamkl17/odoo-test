# -*- coding: utf-8 -*-
"""juni_juli_55_effective_price.py — harga master vs harga efektif POS (READ-ONLY)."""
import os

THRESHOLD = float(os.environ.get("THRESHOLD", "45"))
TARGET = float(os.environ.get("TARGET", "45"))
cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id = pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

rows = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        continue
    _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
    cost = 0.0
    for bl, vals in lines:
        c = bl.product_id
        if not c or Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        cost += sp(c) * (vals.get("qty") or 0.0)
    price = tmpl.list_price or 0.0
    qty, rev = sales.get(p.id, (0.0, 0.0))
    if not price or cost / price * 100 <= THRESHOLD or qty <= 0:
        continue
    eff = rev / qty
    rows.append((tmpl.display_name, price, eff, cost, qty, rev))

rows.sort(key=lambda r: -(r[4] * (r[3] / r[2] * 100 - TARGET) / 100.0))
say("=" * 122)
say("HARGA MASTER vs HARGA EFEKTIF POS — hanya menu HPP>%.0f%% yang benar-benar terjual (READ-ONLY)" % THRESHOLD)
say("=" * 122)
say("%-48s %8s %9s %7s %8s %7s %7s %13s" % (
    "menu", "master", "efektif", "diskon", "HPP", "rasio", "rasioEf", "nilai koreksi"))
say("-" * 122)
tot = 0.0
for nm, price, eff, cost, qty, rev in rows:
    corr = rev * (cost / eff - TARGET / 100.0)
    tot += corr
    say("%-48s %8s %9s %6.1f%% %8s %6.1f%% %6.1f%% %13s" % (
        (nm or "")[:48], money(price), money(eff), (1 - eff / price) * 100,
        money(cost), cost / price * 100, cost / eff * 100, money(corr)))
say("-" * 122)
say("TOTAL nilai koreksi (omzet x (HPP/harga efektif - %.0f%%)) = %s" % (TARGET, money(tot)))
say("jumla menu terjual di atas ambang: %d" % len(rows))
env.cr.rollback()
