# -*- coding: utf-8 -*-
"""juni_juli_23_recon_margin_menu.py — cek kewajaran resep: biaya vs harga per menu (READ-ONLY)."""
from collections import defaultdict

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)


def cost_of(tmpl, qty=1.0):
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))],
                     limit=1)
    if not bom:
        return None
    _b, lines = bom.explode(bom.product_tmpl_id, qty)
    tot = 0.0
    detail = []
    for bl, vals in lines:
        comp = bl.product_id
        if Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
            continue
        q = vals.get("qty") or 0.0
        c = q * (comp.standard_price or 0.0)
        tot += c
        detail.append((comp.display_name, q, comp.standard_price or 0.0, c))
    return tot, detail


say("=" * 104)
say("MARGIN PER MENU  (biaya bahan dari BOM vs harga jual)")
say("%-42s %12s %12s %9s" % ("menu", "biaya", "harga", "margin%"))
rows = []
for b in Bom.search([]):
    tmpl = b.product_tmpl_id
    r = cost_of(tmpl)
    if not r:
        continue
    cost, _d = r
    price = tmpl.list_price or 0.0
    m = (1 - cost / price) * 100 if price else -999
    rows.append((m, tmpl.display_name, cost, price))
rows.sort()
for m, nm, cost, price in rows[:12]:
    say("%-42s %12s %12s %8.1f%%" % ((nm or "")[:42], "{:,.0f}".format(cost),
                                     "{:,.0f}".format(price), m))
say("   ... %d menu total ..." % len(rows))
for m, nm, cost, price in rows[-6:]:
    say("%-42s %12s %12s %8.1f%%" % ((nm or "")[:42], "{:,.0f}".format(cost),
                                     "{:,.0f}".format(price), m))
avg_c = sum(r[2] for r in rows) / len(rows)
avg_p = sum(r[3] for r in rows) / len(rows)
say("")
say("Rata-rata: biaya %s | harga %s | margin %.1f%%" % (
    "{:,.0f}".format(avg_c), "{:,.0f}".format(avg_p), (1 - avg_c / avg_p) * 100))

say("")
say("CONTOH RESEP — 1 menu (fokus kewajaran kuantitas)")
for nm in ("ES TEH", "AYAM GEPREK", "PAKET AYAM CRISPY DADA"):
    t = Prod.search([("name", "ilike", nm)], limit=1).product_tmpl_id
    if not t:
        continue
    r = cost_of(t)
    say("")
    say("   %s | harga jual %s | biaya %s" % (
        t.display_name, "{:,.0f}".format(t.list_price or 0), "{:,.0f}".format(r[0] if r else 0)))
    for cn, q, sp, c in sorted((r[1] if r else []), key=lambda x: -x[3])[:8]:
        say("      %-38s qty=%-12s x %-9s = %s" % (
            (cn or "")[:38], "{:,.2f}".format(q), "{:,.0f}".format(sp), "{:,.0f}".format(c)))

say("")
say("HARGA BAHAN UTAMA (bandingkan dengan pasar)")
for code in ("AYAM CUT 9", "BERAS", "ES KRISTAL", "MINYAK PADAT", "TEPUNG MIX GEYUKSSS",
             "AIR GALON", "SAMBAL KOREK SURABAYA"):
    p = Prod.search([("name", "ilike", code)], limit=1)
    if p:
        say("   %-34s harga=%10s | uom=%s | kategori=%s" % (
            (p.display_name or "")[:34], "{:,.2f}".format(p.standard_price or 0),
            p.uom_id.name, p.categ_id.complete_name))
say("=" * 104)
env.cr.rollback()
