# -*- coding: utf-8 -*-
"""
juni_juli_94_ghost_pairs.py — RECON R1 lanjutan (READ-ONLY).

Untuk tiap pasangan yang namanya berdekatan, bandingkan:
  - komponen BOM (apakah identik?)
  - harga di pricelist "Harga Dasar (Take Away)" dan "Harga Dine In"
  - apakah namanya ada di daftar produk klien (05_products_with_id.csv) / 06_price_update.csv

Sekaligus cari pasangan yang BOM-nya identik tapi namanya berbeda jauh (pasangan ke-5).
"""
import csv, os
from collections import defaultdict

cr = env.cr
PP = env["product.product"]
PT = env["product.template"]
BOM = env["mrp.bom"]
POL = env["pos.order.line"]
PL = env["product.pricelist"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
qty = lambda x: "{:,.4f}".format(float(x or 0)).rstrip("0").rstrip(".")


def read_names(path):
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for k in ("Nama", "name", "Name", "nama", "display_name", "product"):
                if row.get(k):
                    out.add(row[k].strip())
                    break
    return out


KLIEN = read_names("import_data/csv/05_products_with_id.csv")
HARGA = read_names("import_data/csv/06_price_update.csv")

say("=" * 118)
say("RECON R1 LANJUTAN — identitas pasangan & harga per pricelist   (read-only)")
say("=" * 118)
say("")
say("daftar produk klien   : %d nama" % len(KLIEN))
say("daftar harga klien    : %d nama" % len(HARGA))

# ---------------------------------------------------------------- A. fingerprint BOM
say("")
say("[A] PASANGAN DENGAN KOMPONEN BOM IDENTIK (fingerprint semua produk yang punya BOM)")
say("")
cr.execute("""
    SELECT b.product_tmpl_id, pt.name->>'en_US',
           string_agg(bl.product_id::text || 'x' || bl.product_qty::text, '|' ORDER BY bl.product_id)
      FROM mrp_bom b
      JOIN product_template pt ON pt.id = b.product_tmpl_id
      JOIN mrp_bom_line bl ON bl.bom_id = b.id
     GROUP BY 1, 2
""")
fp = defaultdict(list)
for tmpl, nama, sig in cr.fetchall():
    fp[sig].append((tmpl, nama))

pairs = []
for sig, items in fp.items():
    if len(items) < 2:
        continue
    names = [n for _t, n in items]
    # hanya laporkan yang namanya BERIRISAN (kembar sejati), bukan varian potongan
    base = [n.replace("(GEPREK SAMBAL +NASI)", "").strip() for n in names]
    if len(set(base)) < len(names):
        pairs.append(items)

say("   ditemukan %d grup kembar sejati (nama beririsan + BOM identik)" % len(pairs))
say("")

# ---------------------------------------------------------------- B. detail pasangan
say("[B] DETAIL TIAP PASANGAN")
say("")
for items in pairs:
    say("─" * 118)
    for tmpl, nama in items:
        pp = PP.search([("product_tmpl_id", "=", tmpl)], limit=1)
        norder = POL.search_count([("product_id", "=", pp.id)])
        cr.execute("""SELECT COALESCE(SUM(pol.qty),0), COALESCE(SUM(pol.price_subtotal_incl),0)
                        FROM pos_order_line pol WHERE pol.product_id=%s""", (pp.id,))
        q, rev = cr.fetchone()
        inklien = "ADA" if nama.strip() in KLIEN else "—"
        inharga = "ADA" if nama.strip() in HARGA else "—"
        # harga per pricelist
        prc = []
        for pl in PL.search([]):
            itm = env["product.pricelist.item"].search(
                [("pricelist_id", "=", pl.id),
                 "|", ("product_id", "=", pp.id),
                 "&", ("product_tmpl_id", "=", tmpl), ("applied_on", "=", "1_product")], limit=1)
            if itm:
                prc.append("%s=%s" % (pl.name[:22], money(
                    itm.fixed_price if itm.compute_price == "fixed" else itm.price_surcharge)))
        say("   pp=%-5s tmpl=%-5s %-56s" % (pp.id, tmpl, (nama or "")[:56]))
        say("        order=%4d  qty=%-9s omzet=%-16s | produk_klien:%-4s harga_klien:%s" % (
            norder, qty(q), money(rev), inklien, inharga))
        say("        pricelist: %s" % ("  ·  ".join(prc) if prc else "TIDAK ADA HARGA"))
    say("")

# ---------------------------------------------------------------- C. rekomendasi
say("─" * 118)
say("[C] REKOMENDASI SIMPAN / HAPUS (berdasarkan daftar produk klien)")
say("")
for items in pairs:
    keep, drop = [], []
    for tmpl, nama in items:
        (keep if nama.strip() in KLIEN else drop).append((tmpl, nama))
    if len(keep) == 1 and len(drop) >= 1:
        kt, kn = keep[0]
        say("   SIMPAN tmpl=%-5s %s" % (kt, kn))
        for dt, dn in drop:
            say("     hapus tmpl=%-5s %s   ← tidak ada di daftar produk klien" % (dt, dn))
    else:
        say("   ⚠ PERLU KEPUTUSAN — daftar klien tidak memisahkan:")
        for t, n in items:
            say("       tmpl=%-5s %-56s (klien:%s harga:%s)" % (
                t, (n or "")[:56], "ADA" if n.strip() in KLIEN else "—",
                "ADA" if n.strip() in HARGA else "—"))
    say("")
say("=" * 118)
