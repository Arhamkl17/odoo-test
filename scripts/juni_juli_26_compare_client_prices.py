# -*- coding: utf-8 -*-
"""
juni_juli_26_compare_client_prices.py — bandingkan HARGA ASLI KLIEN vs harga di sistem.

Sumber data asli klien : import_data/csv/06_price_update.csv  (kolom "Harga Jual")
Biaya menu             : standard_price (menu) atau biaya BOM bila ada
READ-ONLY.
"""
import csv
import io
from collections import defaultdict

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
say = lambda m="": print(m)

PATH = "import_data/csv/06_price_update.csv"
rows = []
with io.open(PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows.append((r["Nama"].strip(), float(r["Harga Jual"] or 0)))

say("=" * 104)
say("HARGA ASLI KLIEN vs HARGA DI SISTEM SEKARANG   (sumber klien: %s)" % PATH)
say("=" * 104)


def bom_cost(tmpl):
    b = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))],
                   limit=1)
    if not b:
        return None
    _bo, lines = b.explode(b.product_tmpl_id, 1.0)
    tot = 0.0
    for bl, vals in lines:
        comp = bl.product_id
        if Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
            continue
        tot += (vals.get("qty") or 0.0) * (comp.standard_price or 0.0)
    return tot


say("%-40s %10s %10s %10s %11s %11s" % (
    "menu", "harga klien", "harga DB", "selisih%", "margin klien", "margin DB"))
tot_c = tot_d = 0.0
n_up = n_down = n_same = 0
for nama, harga_klien in rows:
    tmpl = env["product.template"].search([("name", "=", nama)], limit=1)
    if not tmpl:
        tmpl = env["product.template"].search([("name", "ilike", nama)], limit=1)
    if not tmpl:
        say("%-40s %10s %10s %10s   (tidak ditemukan di DB)" % (
            nama[:40], "{:,.0f}".format(harga_klien), "-", "-"))
        continue
    harga_db = tmpl.list_price or 0.0
    cost = bom_cost(tmpl)
    if cost is None:
        cost = tmpl.product_variant_id.standard_price or 0.0
    mc = (1 - cost / harga_klien) * 100 if harga_klien else 0
    md = (1 - cost / harga_db) * 100 if harga_db else 0
    delta = (harga_db / harga_klien - 1) * 100 if harga_klien else 0
    tot_c += harga_klien
    tot_d += harga_db
    if delta > 0.5:
        n_up += 1
    elif delta < -0.5:
        n_down += 1
    else:
        n_same += 1
    say("%-40s %10s %10s %9.1f%% %10.1f%% %10.1f%%" % (
        nama[:40], "{:,.0f}".format(harga_klien), "{:,.0f}".format(harga_db), delta, mc, md))

say("")
say("RINGKASAN  (%d menu pada daftar harga klien)" % len(rows))
say("   total harga klien = %s | total harga DB = %s | selisih = %+.1f%%" % (
    "{:,.0f}".format(tot_c), "{:,.0f}".format(tot_d),
    100.0 * (tot_d / tot_c - 1) if tot_c else 0))
say("   harga NAIK di DB: %d menu | TURUN: %d | SAMA: %d" % (n_up, n_down, n_same))

say("")
say("HARGA BAHAN: apakah ada di ekspor klien?")
with io.open("import_data/csv/05_bahan_with_id.csv", encoding="utf-8-sig") as f:
    bh = list(csv.DictReader(f))
nz = [r for r in bh if float(r.get("Modal") or 0) > 0]
say("   baris bahan di ekspor klien : %d" % len(bh))
say("   yang punya Modal > 0          : %d  <-- %s" % (
    len(nz), "KLIEN TIDAK MENGISI BIAYA BAHAN" if not nz else "ada"))
say("   contoh: AYAM CUT 9 Modal=%s | BERAS Modal=%s" % (
    [r["Modal"] for r in bh if r["Nama"] == "AYAM CUT 9"][:1],
    [r["Modal"] for r in bh if r["Nama"] == "BERAS"][:1]))

say("")
say("BIAYA BAHAN YANG DIPAKAI SISTEM SEKARANG (standard_price)")
for code in ("AYAM CUT 9", "BERAS", "ES KRISTAL", "MINYAK PADAT", "TEPUNG MIX GEYUKSSS",
             "AIR GALON", "KEJU MOZARELLA", "TEH MIX"):
    p = Prod.search([("name", "=", code)], limit=1) or Prod.search([("name", "ilike", code)], limit=1)
    if p:
        say("   %-26s %12s / %s" % (p.display_name[:26], "{:,.2f}".format(p.standard_price or 0),
                                    p.uom_id.name))
say("=" * 104)
env.cr.rollback()
