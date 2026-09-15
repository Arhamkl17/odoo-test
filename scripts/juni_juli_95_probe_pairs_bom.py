# -*- coding: utf-8 -*-
"""
juni_juli_95_probe_pairs_bom.py — bandingkan BOM pasangan kembar berdampingan (READ-ONLY).

Pasangan yang diperiksa (§21.1):
  (593 vs 556)  PKG SAMBAL KOREK SURABAYA
  (592 vs 555)  PKG SAMBAL IJO PADANG
  (597 vs 557)  PKG SAMBAL RICA MANADO
  (614 vs 573)  PAKET MEVVAH BERDUA  vs  PKG MEVVAH (...)
"""
cr = env.cr
PP = env["product.product"]
BOM = env["mrp.bom"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
qty = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")

PAIRS = [
    (593, 556, "PKG SAMBAL KOREK SURABAYA"),
    (592, 555, "PKG SAMBAL IJO PADANG"),
    (597, 557, "PKG SAMBAL RICA MANADO"),
    (614, 573, "PAKET MEVVAH BERDUA / PKG MEVVAH"),
]


def bom_map(pp_id):
    pp = PP.browse(pp_id)
    boms = BOM.search([("product_tmpl_id", "=", pp.product_tmpl_id.id)])
    out = {}
    for b in boms:
        for l in b.bom_line_ids:
            key = l.product_id.display_name
            out[key] = out.get(key, 0.0) + l.product_qty
    return pp, len(boms), out


say("=" * 110)
say("PERBANDINGAN BOM PASANGAN KEMBAR   (read-only)")
say("=" * 110)

for a, b, label in PAIRS:
    ppa = PP.browse(a)
    ppb = PP.browse(b)
    say("")
    say("━" * 110)
    say("%s" % label)
    say("   A = pp %-5s %-58s" % (a, (ppa.product_tmpl_id.name or "")[:58]))
    say("   B = pp %-5s %-58s" % (b, (ppb.product_tmpl_id.name or "")[:58]))
    _p, nb_a, ma = bom_map(a)
    _p, nb_b, mb = bom_map(b)
    ka, kb = set(ma), set(mb)
    say("")
    say("   komponen A: %d baris unik (%d BOM)   |   komponen B: %d baris unik (%d BOM)" % (
        len(ma), nb_a, len(mb), nb_b))
    both = sorted(ka & kb)
    only_a = sorted(ka - kb)
    only_b = sorted(kb - ka)
    beda_qty = [(k, ma[k], mb[k]) for k in both if abs(ma[k] - mb[k]) > 1e-6]
    say("   sama di keduanya      : %d" % len(both))
    say("   hanya di A            : %d %s" % (len(only_a), only_a if only_a else ""))
    say("   hanya di B            : %d %s" % (len(only_b), only_b if only_b else ""))
    say("   qty berbeda           : %d" % len(beda_qty))
    for k, va, vb in beda_qty:
        say("       %-56s A=%-10s B=%s" % (k[:56], qty(va), qty(vb)))
    if not only_a and not only_b and not beda_qty:
        say("   ⇒ BOM IDENTIK PERSIS")
    elif not only_a and not only_b:
        say("   ⇒ komponen sama, hanya qty sedikit berbeda")
    # biaya
    for pid, mm in ((a, ma), (b, mb)):
        tot = 0.0
        for nama, q in mm.items():
            rec = PP.search([("display_name", "=", nama)], limit=1)
            if rec:
                tot += rec.standard_price * q
        say("   biaya BOM (standard_price × qty) pp %-5s = %s" % (pid, money(tot)))

    # order & harga
    for pid in (a, b):
        cr.execute("""SELECT COUNT(*), COALESCE(SUM(pol.qty),0),
                             COALESCE(SUM(pol.price_unit),0)/GREATEST(COUNT(*),1)
                        FROM pos_order_line pol WHERE pol.product_id=%s""", (pid,))
        n, q, avg = cr.fetchone()
        say("   pp %-5s  order=%-5d qty=%-10s harga rata-rata POS=%s" % (
            pid, n, qty(q), money(avg)))

say("")
say("=" * 110)
