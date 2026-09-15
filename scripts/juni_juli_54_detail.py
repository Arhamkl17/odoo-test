# -*- coding: utf-8 -*-
"""
juni_juli_54_detail.py — RINCIAN BOM penuh + hitungan opsi koreksi (READ-ONLY).

  su odoo ... " NAMES='MEVVAH,RAMA,MOZAA,BLACKCURRANT' TARGET=45 odoo shell ..." \
      < scripts/juni_juli_54_detail.py
"""
import os

NAMES = [s.strip().upper() for s in os.environ.get("NAMES", "").split(",") if s.strip()]
TARGET = float(os.environ.get("TARGET", "45"))
cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

found = 0
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    nm = (tmpl.display_name or "").upper()
    if not any(n in nm for n in NAMES):
        continue
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        continue
    _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
    comps = []
    for bl, vals in lines:
        c = bl.product_id
        if not c or Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        q = vals.get("qty") or 0.0
        comps.append((q * sp(c), c.display_name, q, c.uom_id.name, sp(c)))
    comps.sort(reverse=True)
    cost = sum(c[0] for c in comps)
    price = tmpl.list_price or 0.0
    qty, rev = sales.get(p.id, (0.0, 0.0))
    found += 1
    say("")
    say("=" * 116)
    say("%s   (id tmpl %s, BOM %s)" % (tmpl.display_name, tmpl.id, bom.display_name))
    say("=" * 116)
    say("harga jual %s | HPP %s | rasio %.1f%% | qty 3bln %.0f | omzet 3bln %s" % (
        money(price), money(cost), cost / price * 100 if price else 0, qty, money(rev)))
    say("harga agar rasio %.0f%% = %s   (naik %+.0f%%)" % (
        TARGET, money(cost / (TARGET / 100.0)), (cost / (TARGET / 100.0) / price - 1) * 100 if price else 0))
    say("biaya harus jadi <= %s (turun %.0f%%) supaya rasio %.0f%% pada harga sekarang" % (
        money(price * TARGET / 100.0),
        (1 - (price * TARGET / 100) / cost) * 100 if cost else 0, TARGET))
    say("")
    say("%-44s %7s %10s %12s %11s %7s" % ("komponen", "qty", "uom", "harga satuan", "biaya", "porsi"))
    say("-" * 116)
    for c, cn, q, uom, spv in comps:
        say("%-44s %7.2f %10s %12s %11s %6.1f%%" % (
            (cn or "")[:44], q, (uom or "")[:10], money(spv), money(c),
            (c / cost * 100) if cost else 0))
    say("-" * 116)
    say("%-44s %7s %10s %12s %11s %6.1f%%" % ("TOTAL", "", "", "", money(cost), 100.0))
    # opsi pangkas: turunkan komponen terbesar
    if comps:
        c0, cn0, q0, uom0, spv0 = comps[0]
        need = cost - price * TARGET / 100.0
        say("   opsi pangkas: komponen terbesar '%s' = %s (%.0f%%). Perlu potong %s." % (
            cn0, money(c0), c0 / cost * 100, money(need)))
        if spv0 > 0:
            say("      -> setara kurangi %.2f %s (dari %.2f)  ATAU hapus %.0f%% komponen ini" % (
                need / spv0, uom0, q0, need / c0 * 100 if c0 else 0))
say("")
say("=" * 116)
say("%d menu ditampilkan untuk pola: %s" % (found, NAMES))
env.cr.rollback()
