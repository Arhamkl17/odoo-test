# -*- coding: utf-8 -*-
"""
juni_juli_96_ghost_decision.py — RECON FINAL R1 (READ-ONLY).

1. Deteksi SEMUA grup dengan komponen BOM identik (qty dinormalisasi, jadi tahan
   terhadap perbedaan penulisan 1 vs 1.0).
2. Untuk tiap produk: jejak di 05_products_with_id.csv (daftar produk klien) dan
   06_price_update.csv (daftar harga klien).
3. Harga di kedua pricelist.
4. Keputusan: mana yang disimpan, mana yang dihapus.
"""
import csv, os
from collections import defaultdict

cr = env.cr
PP = env["product.product"]
BOM = env["mrp.bom"]
POL = env["pos.order.line"]
PL = env["product.pricelist"]
PPI = env["product.pricelist.item"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
num = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")


def read_csv_names(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f)):
            nm = (row.get("Nama") or "").strip()
            if nm:
                out[nm] = row
    return out


KLIEN = read_csv_names("import_data/csv/05_products_with_id.csv")
HARGA = read_csv_names("import_data/csv/06_price_update.csv")

say("=" * 122)
say("RECON FINAL R1   (read-only)")
say("=" * 122)
say("")
say("daftar produk klien : %d nama" % len(KLIEN))
say("daftar harga klien  : %d nama" % len(HARGA))

# --------------------------------------------------- 1. fingerprint BOM (normalisasi)
cr.execute("""
    SELECT b.product_tmpl_id, pt.name->>'en_US',
           string_agg(bl.product_id::text || 'x' || ROUND(bl.product_qty::numeric, 4)::text,
                      '|' ORDER BY bl.product_id)
      FROM mrp_bom b
      JOIN product_template pt ON pt.id = b.product_tmpl_id
      JOIN mrp_bom_line bl ON bl.bom_id = b.id
     GROUP BY 1, 2
""")
fp = defaultdict(list)
for tmpl, nama, sig in cr.fetchall():
    fp[sig].append((tmpl, nama))

say("")
say("[1] SEMUA GRUP DENGAN KOMPONEN BOM IDENTIK")
say("")
grup_all = [v for v in fp.values() if len(v) >= 2]
grup = []
for items in grup_all:
    base = [n.replace("(GEPREK SAMBAL +NASI)", "").strip().upper() for _t, n in items]
    if len(set(base)) < len(base):
        grup.append(items)
say("   grup dgn BOM identik      : %d" % len(grup_all))
say("   di antaranya nama kembar  : %d  ← kandidat R1" % len(grup))
for items in grup:
    say("       %s" % "  ▲  ".join("%s(%s)" % (n[:38], t) for t, n in items))


def prc(pp_id, tmpl_id):
    out = []
    for pl in PL.search([]):
        it = PPI.search([("pricelist_id", "=", pl.id),
                         "|", ("product_id", "=", pp_id),
                         "&", ("product_tmpl_id", "=", tmpl_id), ("applied_on", "=", "1_product")],
                        limit=1)
        if it:
            out.append((pl.name, it.fixed_price))
    return out


# --------------------------------------------------- 2. detail
say("")
say("[2] DETAIL PER PRODUK — jejak klien & harga")
say("")
say("%-6s %-5s %-50s %-6s %-6s %10s %12s %12s" % (
    "pp", "tmpl", "nama", "klien", "harga", "lst_price", "TakeAway", "DineIn"))
say("-" * 122)
allids = []
for items in grup:
    for tmpl, nama in items:
        pp = PP.search([("product_tmpl_id", "=", tmpl)], limit=1)
        allids.append((pp.id, tmpl, nama))
for pid, tmpl, nama in sorted(allids, key=lambda x: x[2]):
    p = prc(pid, tmpl)
    d = dict(p)
    ta = d.get("Harga Dasar (Take Away)")
    di = d.get("Harga Dine In")
    say("%-6s %-5s %-50s %-6s %-6s %10s %12s %12s" % (
        pid, tmpl, (nama or "")[:50],
        "ADA" if (nama or "").strip() in KLIEN else "—",
        "ADA" if (nama or "").strip() in HARGA else "—",
        money(PP.browse(pid).lst_price),
        money(ta) if ta is not None else "—",
        money(di) if di is not None else "—"))

# --------------------------------------------------- 3. volume per produk
say("")
say("[3] VOLUME DI POS (Juni–Agustus) & DAMPAK PENGGABUNGAN")
say("")
say("%-6s %-50s %8s %10s %16s" % ("pp", "nama", "order", "qty", "omzet"))
say("-" * 122)
tot_semua = {}
for items in grup:
    for tmpl, nama in items:
        pp = PP.search([("product_tmpl_id", "=", tmpl)], limit=1)
        cr.execute("""SELECT COUNT(*), COALESCE(SUM(pol.qty),0),
                             COALESCE(SUM(pol.price_subtotal_incl),0)
                        FROM pos_order_line pol WHERE pol.product_id=%s""", (pp.id,))
        n, q, rev = cr.fetchone()
        tot_semua[(pp.id, tmpl, nama)] = (n, float(q), float(rev))
        say("%-6s %-50s %8d %10s %16s" % (pp.id, (nama or "")[:50], n, num(q), money(rev)))
    say("")

# --------------------------------------------------- 4. rekomendasi
say("[4] REKOMENDASI")
say("")
for items in grup:
    keep = [(t, n) for t, n in items if n.strip() in KLIEN]
    drop = [(t, n) for t, n in items if n.strip() not in KLIEN]
    if len(keep) == 1 and drop:
        kt, kn = keep[0]
        kp = PP.search([("product_tmpl_id", "=", kt)], limit=1)
        say("   ✔ SIMPAN tmpl=%-5s pp=%-5s %s" % (kt, kp.id, kn))
        for dt, dn in drop:
            dp = PP.search([("product_tmpl_id", "=", dt)], limit=1)
            _, qd, revd = tot_semua.get((dp.id, dt, dn), (0, 0, 0))
            _, qk, revk = tot_semua.get((kp.id, kt, kn), (0, 0, 0))
            say("     ✘ hapus tmpl=%-5s pp=%-5s %-50s → %d baris dipindah" % (
                dt, dp.id, dn[:50], tot_semua.get((dp.id, dt, dn), (0,))[0]))
            say("       setelah gabung: qty %s + %s = %s | omzet %s + %s = %s" % (
                num(qk), num(qd), num(qk + qd), money(revk), money(revd), money(revk + revd)))
    else:
        say("   ⚠ PERLU KEPUTUSAN MANUAL: %s" % "  ▲  ".join("%s(%s)" % (n[:40], t) for t, n in items))
    say("")
say("=" * 122)
