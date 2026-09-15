# -*- coding: utf-8 -*-
"""
juni_juli_51_diag_bom_tinggi.py — BEDAH BOM menu yang HPP-nya tinggi (READ-ONLY).

Untuk tiap menu di atas ambang: harga perlu jadi berapa agar HPP turun ke target,
dan komponen mana yang paling mahal (kandidat koreksi porsi/resep).

  su odoo ... " THRESHOLD=45 TARGET=45 TOP=30 odoo shell ..." < scripts/juni_juli_51_diag_bom_tinggi.py
"""
import os
from collections import defaultdict

THRESHOLD = float(os.environ.get("THRESHOLD", "45"))
TARGET = float(os.environ.get("TARGET", "45"))
TOP = int(os.environ.get("TOP", "30"))
cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


def explode(tmpl):
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id),
                      ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        return None
    _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
    comps = []
    for bl, vals in lines:
        c = bl.product_id
        if not c:
            continue
        if Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        q = vals.get("qty") or 0.0
        comps.append((q * sp(c), c.display_name, q, c.uom_id.name, sp(c)))
    comps.sort(reverse=True)
    return comps


cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

rows = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    price = tmpl.list_price or 0.0
    comps = explode(tmpl)
    if not comps or not price:
        continue
    cost = sum(c[0] for c in comps)
    if cost / price * 100 <= THRESHOLD:
        continue
    qty, rev = sales.get(p.id, (0.0, 0.0))
    rows.append({"tmpl": tmpl, "price": price, "cost": cost, "qty": qty,
                 "rev": rev, "comps": comps})

rows.sort(key=lambda r: -r["rev"])
say("=" * 122)
say("BEDAH BOM — %d menu dengan HPP > %.0f%%  (diurut dampak omzet 3 bulan)" % (len(rows), THRESHOLD))
say("   target HPP %.0f%% -> kolom 'harga ideal'. nilai koreksi = omzet x (HPP%%-%.0f%%)" % (TARGET, TARGET))
say("=" * 122)
for i, r in enumerate(rows[:TOP], 1):
    ratio = r["cost"] / r["price"] * 100
    ideal = r["cost"] / (TARGET / 100.0)
    say("")
    say("%2d. %-52s harga %9s  HPP %9s  %6.1f%%   qty %5.0f  omzet %12s" % (
        i, (r["tmpl"].display_name or "")[:52], money(r["price"]), money(r["cost"]),
        ratio, r["qty"], money(r["rev"])))
    say("    perlu harga >= %s (naik %+.0f%%)  |  atau pangkas biaya %s (-%.0f%%)  |  nilai koreksi %s" % (
        money(ideal), (ideal / r["price"] - 1) * 100,
        money(r["cost"] - r["price"] * TARGET / 100.0),
        (1 - (r["price"] * TARGET / 100.0) / r["cost"]) * 100 if r["cost"] else 0,
        money(r["rev"] * (ratio - TARGET) / 100.0)))
    for c, nm, q, uom, spv in r["comps"][:4]:
        say("       - %-40s %10s = %5.2f %-5s x %s" % (
            (nm or "")[:40], money(c), q, (uom or "")[:5], money(spv)))
    if len(r["comps"]) > 4:
        rest = sum(c[0] for c in r["comps"][4:])
        say("       - (+%d komponen lain) %s" % (len(r["comps"]) - 4, money(rest)))
say("")
say("=" * 122)
say("TOTAL %d menu: omzet %s | HPP %s" % (
    len(rows), money(sum(r["rev"] for r in rows)), money(sum(comps_cost(r) for r in rows)) if False else
    money(sum(r["rev"] * (r["cost"] / r["price"]) for r in rows))))
env.cr.rollback()
