# -*- coding: utf-8 -*-
"""
juni_juli_58_dup_bom.py — DETEKSI MENU KEMBAR berbasis RESEP (READ-ONLY).

Menu dianggap kembar bila himpunan komponen BOM-nya (komponen + kuantitas) identik,
walau nama/harga/qty berbeda. Ini definisi yang benar — bukan dari angka penjualan.

  su odoo ... < scripts/juni_juli_58_dup_bom.py
"""
from collections import defaultdict
import os

SIG_ROUND = int(os.environ.get("ROUND", "3"))
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
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
sales = {int(p): (float(q or 0), float(r or 0)) for p, q, r in cr.fetchall() if p}

groups = defaultdict(list)
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        continue
    _b, lines = bom.explode(bom.product_tmpl_id, 1.0)
    sig, cost = [], 0.0
    for bl, vals in lines:
        c = bl.product_id
        if not c or Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
            continue
        q = round(vals.get("qty") or 0.0, SIG_ROUND)
        sig.append((c.id, q))
        cost += sp(c) * q
    if not sig:
        continue
    key = tuple(sorted(sig))
    qty, rev = sales.get(p.id, (0.0, 0.0))
    groups[key].append({"pid": p.id, "nm": tmpl.display_name or "", "price": tmpl.list_price or 0.0,
                        "cost": cost, "qty": qty, "rev": rev, "ncomp": len(sig),
                        "bom": bom.display_name})

say("=" * 126)
say("MENU DENGAN RESEP (BOM) IDENTIK — kandidat duplikat   (pembulatan qty %d desimal)" % SIG_ROUND)
say("=" * 126)
dups = {k: v for k, v in groups.items() if len(v) > 1}
n_prod = 0
for k, v in sorted(dups.items(), key=lambda kv: -sum(x["rev"] for x in kv[1])):
    n_prod += len(v)
    rev = sum(x["rev"] for x in v)
    say("")
    say("-- %d template, resep %d komponen, biaya %s, total omzet %s" % (
        len(v), v[0]["ncomp"], money(v[0]["cost"]), money(rev)))
    for x in sorted(v, key=lambda y: -y["rev"]):
        say("   id=%-5d %-52s harga %8s  qty %6.0f  omzet %13s" % (
            x["pid"], x["nm"][:52], money(x["price"]), x["qty"], money(x["rev"])))

say("")
say("=" * 126)
say("RINGKASAN")
say("  %d kelompok resep identik, melibatkan %d template menu" % (len(dups), n_prod))
say("  omzet 3 bulan yang terlibat: %s" % money(sum(sum(x['rev'] for x in v) for v in dups.values())))
say("  menu ber-BOM total: %d" % sum(len(v) for v in groups.values()))
say("")
say("Untuk tiap kelompok, apakah KEMBAR PENUH (satu menu terdaftar 2x) atau varian sah —")
say("dilihat dari harga & sebaran omzet:")
for k, v in sorted(dups.items(), key=lambda kv: -sum(x["rev"] for x in kv[1])):
    prices = sorted(set(round(x["price"]) for x in v))
    nol = [x["nm"] for x in v if x["qty"] == 0]
    say("   %-70s harga %s%s" % (
        " | ".join(x["nm"][:32] for x in sorted(v, key=lambda y: -y["rev"])),
        prices, "   [ada yg qty 0]" if nol else ""))
env.cr.rollback()
