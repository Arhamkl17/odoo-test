# -*- coding: utf-8 -*-
"""
juni_juli_62_price_sanity.py — TIGA SUMBER HARGA dibandingkan (READ-ONLY).

  1. harga KLIEN   : import_data/csv/06_price_update.csv (daftar harga resmi klien)
  2. harga MASTER  : product.template.list_price di sistem sekarang
  3. harga POS     : rata-rata price_unit yang benar-benar dipakai Juni-Agustus

  su odoo ... < scripts/juni_juli_62_price_sanity.py
"""
import csv
import io

CSV_PATH = "import_data/csv/06_price_update.csv"
cr = env.cr
Prod = env["product.product"]
Bom = env["mrp.bom"]
say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))


def sp(p):
    v = p.standard_price
    return float((v.get("1") if isinstance(v, dict) else v) or 0.0)


klien = {}
with io.open(CSV_PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        nm = (r.get("Nama") or "").strip().upper()
        try:
            klien[nm] = float((r.get("Harga Jual") or "0").strip() or 0)
        except ValueError:
            klien[nm] = 0.0

cr.execute("""
    SELECT pol.product_id, AVG(pol.price_unit), SUM(pol.qty), SUM(pol.price_subtotal)
      FROM pos_order_line pol JOIN pos_order po ON po.id=pol.order_id
     WHERE po.state IN ('paid','done','invoiced')
       AND po.date_order >= '2026-06-01' AND po.date_order < '2026-09-01'
     GROUP BY 1""")
pos = {int(p): (float(a or 0), float(q or 0), float(r or 0)) for p, a, q, r in cr.fetchall() if p}

say("=" * 128)
say("TIGA SUMBER HARGA — produk yang ada di daftar harga resmi klien (%d produk)" % len(klien))
say("=" * 128)
say("%-44s %9s %9s %9s %9s %8s %9s" % (
    "menu", "KLIEN", "MASTER", "POS", "selisih", "HPP", "HPP@klien"))
say("-" * 128)

cocok_master = cocok_pos = beda = 0
n_master_naik = n_master_turun = 0
rows = []
for p in Prod.search([("sale_ok", "=", True), ("available_in_pos", "=", True)]):
    tmpl = p.product_tmpl_id
    nm = (tmpl.display_name or "").upper().strip()
    if nm not in klien:
        continue
    kp = klien[nm]
    master = tmpl.list_price or 0.0
    avg, qty, rev = pos.get(p.id, (0.0, 0.0, 0.0))
    bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))], limit=1)
    cost = 0.0
    if bom:
        _b, lines = bom.explode(tmpl, 1.0)
        for bl, vals in lines:
            c = bl.product_id
            if not c or Bom.search_count([("product_tmpl_id", "=", c.product_tmpl_id.id)]):
                continue
            cost += sp(c) * (vals.get("qty") or 0.0)
    rows.append((nm, kp, master, avg, cost, qty))

rows.sort(key=lambda r: -(r[2] - r[1]))
for nm, kp, master, avg, cost, qty in rows:
    d = master - kp
    if abs(d) < 0.5:
        cocok_master += 1
        tag = "= klien"
    elif d > 0:
        n_master_naik += 1
        tag = "+%.0f%%" % (d / kp * 100)
    else:
        n_master_turun += 1
        tag = "%.0f%%" % (d / kp * 100)
    if abs(avg - kp) < 0.5:
        cocok_pos += 1
    else:
        beda += 1
    say("%-44s %9s %9s %9s %9s %8s %8s" % (
        nm[:44], money(kp), money(master), money(avg) if avg else "-", tag,
        money(cost), ("%.0f%%" % (cost / kp * 100)) if kp else "-"))

say("-" * 128)
say("")
say("KESIMPULAN")
say("  master == harga klien         : %d produk" % cocok_master)
say("  master DI ATAS harga klien    : %d produk  <-- agent menaikkan harga" % n_master_naik)
say("  master DI BAWAH harga klien   : %d produk" % n_master_turun)
say("  harga POS == harga klien      : %d produk" % cocok_pos)
say("  harga POS != harga klien      : %d produk" % beda)
say("")
say("  rata-rata rasio HPP pada harga KLIEN: %.1f%%" % (
    sum((r[4] / r[1] * 100) for r in rows if r[1]) / max(1, len([r for r in rows if r[1]]))))
say("  rata-rata rasio HPP pada harga MASTER: %.1f%%" % (
    sum((r[4] / r[2] * 100) for r in rows if r[2]) / max(1, len([r for r in rows if r[2]]))))
env.cr.rollback()
