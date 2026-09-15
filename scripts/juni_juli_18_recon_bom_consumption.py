# -*- coding: utf-8 -*-
"""
juni_juli_18_recon_bom_consumption.py — hitung kebutuhan konsumsi bahan dari BOM.

READ-ONLY. Untuk setiap bulan: ledakkan (explode) BOM setiap menu yang terjual menjadi
komponen dasar, kalikan dengan qty terjual, lalu nilai dengan standard_price komponen.
Hasilnya = HPP teoretis per bulan + daftar komponen terbesar.
"""
from collections import defaultdict

cr = env.cr
POSL = env["pos.order.line"]
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)

M = [("Jun", "2026-06-01", "2026-07-01"),
     ("Jul", "2026-07-01", "2026-08-01"),
     ("Agu", "2026-08-01", "2026-09-01")]

say("=" * 100)
say("A. Jumlah POS order line & BOM header")
say("   mrp.bom total=%d | tipe: %s" % (
    Bom.search_count([]),
    {t or "normal": Bom.search_count([("type", "=", t)]) for t in ("phantom", "normal")}))
say("   produk dgn BOM: %d" % len(Bom.search([]).mapped("product_tmpl_id")))


def explode(prod_tmpl, qty, depth=0, seen=None):
    """Kembalikan {component_product_id: qty} untuk qty unit produk jadi."""
    seen = seen or set()
    out = defaultdict(float)
    if depth > 5 or prod_tmpl.id in seen:
        return out
    bom = Bom.search([("product_tmpl_id", "=", prod_tmpl.id),
                      ("type", "in", ("phantom", "normal"))], limit=1)
    if not bom:
        out[prod_tmpl.product_variant_id.id] += qty
        return out
    factor = qty / (bom.product_qty or 1.0)
    seen = seen | {prod_tmpl.id}
    for bl in bom.bom_line_ids:
        sub_qty = bl.product_qty * factor
        sub_tmpl = bl.product_id.product_tmpl_id
        if Bom.search_count([("product_tmpl_id", "=", sub_tmpl.id)]):
            for k, v in explode(sub_tmpl, sub_qty, depth + 1, seen).items():
                out[k] += v
        else:
            out[bl.product_id.id] += sub_qty
    return out


for name, a, b in M:
    lines = POSL.search([("order_id.date_order", ">=", a), ("order_id.date_order", "<", b),
                         ("order_id.state", "!=", "cancel")])
    comp = defaultdict(float)
    no_bom = defaultdict(float)
    for l in lines:
        tmpl = l.product_id.product_tmpl_id
        q = l.qty or 0.0
        if Bom.search_count([("product_tmpl_id", "=", tmpl.id)]):
            for k, v in explode(tmpl, q).items():
                comp[k] += v
        else:
            no_bom[tmpl.display_name] += q
    val = 0.0
    for pid, q in comp.items():
        p = Prod.browse(pid)
        val += q * (p.standard_price or 0.0)
    say("")
    say("[%s] order line=%d | komponen unik=%d | qty total=%s" % (
        name, len(lines), len(comp), "{:,.2f}".format(sum(comp.values()))))
    say("     HPP teoretis (standard_price) = %s" % "{:,.2f}".format(val))
    if no_bom:
        say("     TERJUAL TANPA BOM: %d produk, %s unit -> %s" % (
            len(no_bom), "{:,.0f}".format(sum(no_bom.values())),
            list(no_bom.items())[:4]))
    top = sorted(comp.items(), key=lambda x: -(x[1] * (Prod.browse(x[0]).standard_price or 0)))[:6]
    for pid, q in top:
        p = Prod.browse(pid)
        sp = p.standard_price or 0.0
        say("       %-40s qty=%14s x %10s = %16s" % (
            (p.display_name or "")[:40], "{:,.1f}".format(q), "{:,.0f}".format(sp),
            "{:,.2f}".format(q * sp)))
say("=" * 100)
env.cr.rollback()
