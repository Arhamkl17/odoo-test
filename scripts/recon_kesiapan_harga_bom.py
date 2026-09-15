# -*- coding: utf-8 -*-
"""
recon_kesiapan_harga_bom.py — INSPEKSI KESIAPAN HARGA & BOM (READ-ONLY).

Tujuan: memotret kondisi master data (harga jual, pricelist, BOM, UOM, biaya
komponen) SETELAH RESET TOTAL 13 Sep 2026, dan mencari anomali yang harus
dibereskan sebelum data dummy 3 bulan dibuat.

Tidak menulis apa pun ke DB (`env.cr.rollback()` di akhir).

  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
    < scripts/recon_kesiapan_harga_bom.py
"""
import collections
import datetime
import math
import re

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
SEP = "=" * 120
SUB = "-" * 120

PT = env["product.template"]
PP = env["product.product"]
PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]
BOM = env["mrp.bom"]
CFG = env["pos.config"]
PRE = env["pos.preset"]

NORMAL = "Harga Normal"
PLATFORM = "Harga Platform Online"
TARGET = 45.0
TOL = 0.5  # toleransi pembulatan Rp 500


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def find_pl(name, active_only=False):
    dom = [("name", "=", name)]
    if not active_only:
        return PL.with_context(active_test=False).search(dom, limit=1)
    return PL.search(dom, limit=1)


def item_map(pl):
    """{product_tmpl_id: (fixed_price, compute_price, item_id)} — hanya item level template."""
    out = {}
    if not pl:
        return out
    for it in PLI.search([("pricelist_id", "=", pl.id)]):
        tid = it.product_tmpl_id.id or (it.product_id.product_tmpl_id.id if it.product_id else None)
        if tid:
            out.setdefault(tid, []).append(
                (float(it.fixed_price or 0), it.compute_price, it.id))
    return out


def ceil500(x):
    return math.ceil(float(x) / 500.0) * 500


pl_normal = find_pl(NORMAL)
pl_platform = find_pl(PLATFORM)
m_norm = item_map(pl_normal)
m_plat = item_map(pl_platform)

say(SEP)
say("INSPEKSI KESIAPAN HARGA & BOM — DB Test1 — %s — READ-ONLY" % datetime.date.today())
say(SEP)

# =====================================================================
say("")
say("[0] KONFIGURASI POS / PRICELIST / PRESET")
say("")
for pl in PL.with_context(active_test=False).search([]):
    say("   pricelist id=%-3s %-24s aktif=%-5s item=%d" % (
        pl.id, pl.name, pl.active, PLI.search_count([("pricelist_id", "=", pl.id)])))
say("")
for c in CFG.with_context(active_test=False).search([]):
    say("   pos.config id=%-3s %-22s aktif=%-5s pricelist=%-24s use_pricelist=%-5s preset(default=%s n=%d)" % (
        c.id, c.name, c.active, c.pricelist_id.name or "(kosong)",
        bool(c.use_pricelist), c.default_preset_id.name or "-", len(c.available_preset_ids)))
say("")
for pr in PRE.search([]):
    say("   pos.preset id=%-3s %-14s pricelist=%s" % (
        pr.id, pr.name, pr.pricelist_id.name or "(KOSONG)"))

# =====================================================================
# Produk POS
cr.execute("""
    SELECT pp.id, pt.id, (pt.name->>'en_US'), pt.list_price, pt.type,
           COALESCE(pc.name, ''), COALESCE((uu.name->>'en_US'), ''),
           pt.active, pt.sale_ok, pt.available_in_pos
      FROM product_template pt
      JOIN product_product pp ON pp.product_tmpl_id = pt.id
      LEFT JOIN product_category pc ON pc.id = pt.categ_id
      LEFT JOIN uom_uom uu ON uu.id = pt.uom_id
     WHERE pt.available_in_pos AND pt.active AND pt.sale_ok
     ORDER BY 3
""")
pos_rows = []
for pp_id, tmpl_id, nama, list_price, ptype, categ, uom, *_ in cr.fetchall():
    pos_rows.append(dict(pp=pp_id, tmpl=tmpl_id, nama=nama, list=float(list_price or 0),
                         tipe=ptype, categ=categ, uom=uom))
POS_TMPL = {r["tmpl"] for r in pos_rows}

# =====================================================================
say("")
say("[1] HARGA — list_price vs item pricelist")
say("")
a_missing_norm = [r for r in pos_rows if r["tmpl"] not in m_norm]
a_missing_plat = [r for r in pos_rows if r["tmpl"] not in m_plat]
a_drift = [r for r in pos_rows if r["tmpl"] in m_norm and abs(m_norm[r["tmpl"]][0][0] - r["list"]) > TOL]
a_plat_bad = []
for r in pos_rows:
    if r["tmpl"] not in m_norm or r["tmpl"] not in m_plat:
        continue
    if r["categ"] == "Services" or r["tipe"] == "service":
        continue
    px_n = m_norm[r["tmpl"]][0][0]
    px_p = m_plat[r["tmpl"]][0][0]
    if abs(px_p - ceil500(px_n * 1.10)) > TOL:
        a_plat_bad.append((r, px_n, px_p, ceil500(px_n * 1.10)))

say("   A1. produk POS tanpa item `%s`      : %d" % (NORMAL, len(a_missing_norm)))
for r in a_missing_norm:
    say("        - %-52s list=%s" % (r["nama"][:52], money(r["list"])))
say("   A2. produk POS tanpa item `%s` : %d" % (PLATFORM, len(a_missing_plat)))
for r in a_missing_plat:
    say("        - %-52s list=%s" % (r["nama"][:52], money(r["list"])))
say("   A3. list_price != harga %s (drift)    : %d" % (NORMAL, len(a_drift)))
for r in a_drift[:25]:
    say("        - %-52s list=%s  normal=%s" % (
        r["nama"][:52], money(r["list"]), money(m_norm[r["tmpl"]][0][0])))
say("   A4. harga platform != ceil500(normal x1,10) : %d" % len(a_plat_bad))
for r, px_n, px_p, exp in a_plat_bad:
    say("        - %-52s normal=%s platform=%s (harus %s)" % (
        r["nama"][:52], money(px_n), money(px_p), money(exp)))

# item pricelist yatim (produk non-POS / arsip)
say("")
say("   A5. item pricelist yatim (template non-POS/arsip):")
cr.execute("""
    SELECT pi.id, (pt.name->>'en_US'), pt.active,
           pt.available_in_pos, pt.sale_ok, pi.fixed_price, pl.name->>'en_US'
      FROM product_pricelist_item pi
      JOIN product_template pt ON pt.id = pi.product_tmpl_id
      JOIN product_pricelist pl ON pl.id = pi.pricelist_id
     WHERE NOT (pt.active AND pt.available_in_pos AND pt.sale_ok)
     ORDER BY 2
""")
orphan_items = cr.fetchall()
for iid, pname, act, ipos, sok, px, plname in orphan_items:
    say("        - [%s] %-46s aktif=%-5s POS=%-5s sale=%-5s harga=%s" % (
        plname[:18], (pname or "")[:46], act, ipos, sok, money(px)))
say("        → %d item" % len(orphan_items))

# duplikat item per pricelist
say("")
say("   A6. duplikat item per produk per pricelist:")
cr.execute("""
    SELECT pl.name->>'en_US', (pt.name->>'en_US'), count(*)
      FROM product_pricelist_item pi
      JOIN product_template pt ON pt.id = pi.product_tmpl_id
      JOIN product_pricelist pl ON pl.id = pi.pricelist_id
     GROUP BY 1,2 HAVING count(*) > 1 ORDER BY 3 DESC, 2
""")
dups = cr.fetchall()
for plname, pname, n in dups:
    say("        - [%s] %-48s %d item" % (plname[:18], pname[:48], n))
say("        → %d produk" % len(dups))

# harga nol / tidak wajar
say("")
say("   A7. produk POS harga <= 100 (non-Services):")
cheap = [r for r in pos_rows if r["list"] <= 100 and r["categ"] != "Services"]
for r in cheap:
    say("        - %-52s %s [%s/%s]" % (r["nama"][:52], money(r["list"]), r["categ"], r["uom"]))
say("        → %d produk" % len(cheap))

# platform < normal
say("")
say("   A8. harga platform <= harga normal (markup hilang):")
bad_markup = []
for r in pos_rows:
    if r["tmpl"] in m_norm and r["tmpl"] in m_plat and r["categ"] != "Services":
        if m_plat[r["tmpl"]][0][0] <= m_norm[r["tmpl"]][0][0]:
            bad_markup.append((r, m_norm[r["tmpl"]][0][0], m_plat[r["tmpl"]][0][0]))
for r, a, b in bad_markup:
    say("        - %-52s normal=%s platform=%s" % (r["nama"][:52], money(a), money(b)))
say("        → %d produk" % len(bad_markup))

# =====================================================================
say("")
say("[2] BOM — struktur & kelengkapan")
say("")
cr.execute("""
    SELECT b.id, b.product_tmpl_id, (bt.name->>'en_US'), b.type, bt.active,
           bt.available_in_pos, bt.sale_ok, COALESCE((buu.name->>'en_US'),''),
           COALESCE((tuu.name->>'en_US'),'')
      FROM mrp_bom b
      JOIN product_template bt ON bt.id = b.product_tmpl_id
      LEFT JOIN uom_uom buu ON buu.id = b.product_uom_id
      LEFT JOIN uom_uom tuu ON tuu.id = bt.uom_id
     ORDER BY 3
""")
boms = collections.defaultdict(list)
bom_meta = {}
for bid, tmpl, nama, btype, act, ipos, sok, buom, tuom in cr.fetchall():
    boms[tmpl].append(bid)
    bom_meta[bid] = dict(bid=bid, tmpl=tmpl, nama=nama, btype=btype, act=act,
                         ipos=ipos, sok=sok, buom=buom, tuom=tuom)

say("   B1. produk POS TANPA BOM: %d" % len([r for r in pos_rows if r["tmpl"] not in boms]))
for r in [r for r in pos_rows if r["tmpl"] not in boms]:
    say("        - %-52s [%s] %s" % (r["nama"][:52], r["categ"], money(r["list"])))
say("")
say("   B2. produk POS dengan >1 BOM:")
multi = [(r, len(boms[r["tmpl"]])) for r in pos_rows if len(boms.get(r["tmpl"], [])) > 1]
for r, n in multi:
    say("        - %-52s %d BOM" % (r["nama"][:52], n))
say("        → %d produk" % len(multi))
say("")
say("   B3. BOM tanpa baris / BOM produk arsip / non-POS:")
nol = [(b, m) for b, m in bom_meta.items()
       if not env["mrp.bom"].browse(b).bom_line_ids]
for b, m in nol:
    say("        - BOM %s %-46s (tanpa baris)" % (b, m["nama"][:46]))
say("        → %d BOM tanpa baris" % len(nol))
yatim_bom = [m for b, m in bom_meta.items() if not (m["act"] and m["ipos"] and m["sok"])]
for m in yatim_bom:
    say("        - BOM %-5s %-46s aktif=%-5s POS=%-5s sale=%-5s" % (
        m["bid"], m["nama"][:46], m["act"], m["ipos"], m["sok"]))
say("        → %d BOM menunjuk template non-POS/arsip" % len(yatim_bom))

say("")
say("   B4. BOM header UOM != UOM produk:")
uom_beda = [(m, ) for b, m in bom_meta.items() if m["buom"] and m["tuom"] and m["buom"] != m["tuom"]]
for m, in uom_beda:
    say("        - %-46s header=%s produk=%s" % (m["nama"][:46], m["buom"], m["tuom"]))
say("        → %d BOM" % len(uom_beda))

say("")
say("   B5. baris BOM qty <= 0:")
cr.execute("""
    SELECT b.id, (bt.name->>'en_US'), (ct.name->>'en_US'), l.product_qty
      FROM mrp_bom_line l
      JOIN mrp_bom b ON b.id = l.bom_id
      JOIN product_template bt ON bt.id = b.product_tmpl_id
      JOIN product_product cp ON cp.id = l.product_id
      JOIN product_template ct ON ct.id = cp.product_tmpl_id
     WHERE l.product_qty <= 0 ORDER BY 2
""")
qty0 = cr.fetchall()
for bid, pname, cname, q in qty0:
    say("        - %-42s → %-34s qty=%s" % ((pname or "")[:42], (cname or "")[:34], q))
say("        → %d baris" % len(qty0))

say("")
say("   B6. baris BOM memakai KOMPONEN yang juga produk POS/menu (resep datar):")
cr.execute("""
    SELECT DISTINCT (bt.name->>'en_US'), (ct.name->>'en_US')
      FROM mrp_bom_line l
      JOIN mrp_bom b ON b.id = l.bom_id
      JOIN product_template bt ON bt.id = b.product_tmpl_id
      JOIN product_product cp ON cp.id = l.product_id
      JOIN product_template ct ON ct.id = cp.product_tmpl_id
     WHERE ct.available_in_pos AND ct.sale_ok AND ct.active
     ORDER BY 2
""")
datar = cr.fetchall()
for pname, cname in datar:
    say("        - %-42s memakai %s" % ((pname or "")[:42], cname))
say("        → %d pasangan" % len(datar))

say("")
say("   B7. baris BOM UOM tidak sama dengan UOM komponen:")
cr.execute("""
    SELECT (bt.name->>'en_US'), (ct.name->>'en_US'), (luu.name->>'en_US'),
           (cuu.name->>'en_US'), l.product_qty
      FROM mrp_bom_line l
      JOIN mrp_bom b ON b.id = l.bom_id
      JOIN product_template bt ON bt.id = b.product_tmpl_id
      JOIN product_product cp ON cp.id = l.product_id
      JOIN product_template ct ON ct.id = cp.product_tmpl_id
      LEFT JOIN uom_uom luu ON luu.id = l.product_uom_id
      LEFT JOIN uom_uom cuu ON cuu.id = ct.uom_id
     WHERE l.product_uom_id IS NOT NULL AND ct.uom_id IS NOT NULL
       AND l.product_uom_id <> ct.uom_id
     ORDER BY 1,2
""")
uom_line = cr.fetchall()
for pname, cname, lu, cu, q in uom_line:
    say("        - %-36s → %-30s baris=%-6s komponen=%-6s qty=%s" % (
        (pname or "")[:36], (cname or "")[:30], lu, cu, q))
say("        → %d baris" % len(uom_line))

# =====================================================================
say("")
say("[3] BIAYA KOMPONEN (daun BOM)")
say("")
cr.execute("""
    SELECT DISTINCT cp.id, (ct.name->>'en_US'), COALESCE((cp.standard_price->>'1')::numeric,0),
           COALESCE(pc.name,''), COALESCE((cuu.name->>'en_US'),'')
      FROM mrp_bom_line l
      JOIN mrp_bom b ON b.id=l.bom_id
      JOIN product_product cp ON cp.id=l.product_id
      JOIN product_template ct ON ct.id=cp.product_tmpl_id
      LEFT JOIN product_category pc ON pc.id=ct.categ_id
      LEFT JOIN uom_uom cuu ON cuu.id=ct.uom_id
     WHERE b.active
     ORDER BY 3, 2
""")
komp = cr.fetchall()
say("   total komponen unik dipakai BOM aktif : %d" % len(komp))
zero = [k for k in komp if float(k[2] or 0) <= 0]
for cp_id, nama, sp, cat, uom in zero:
    say("   C1. BIAYA 0 : pp=%-4s %-40s [%s/%s] standard_price=%s" % (
        cp_id, (nama or "")[:40], cat, uom, money(sp)))
say("        → %d komponen tanpa biaya" % len(zero))
say("")
say("   C2. komponen yang masih dijual di POS (seharusnya bahan saja):")
salah = [(cp_id, nama, cat) for cp_id, nama, sp, cat, uom in komp
         if cp_id in set(env["product.product"].search(
             [("product_tmpl_id.available_in_pos", "=", True)]).ids)]
if not salah:
    say("        (tidak ada)")
for cp_id, nama, cat in salah:
    say("        - pp=%-4s %-46s [%s]" % (cp_id, (nama or "")[:46], cat))
say("        → %d komponen" % len(salah))

# =====================================================================
say("")
say("[4] DUPLIKAT PRODUK (nama kembar / resep identik)")
say("")
cr.execute("""
    SELECT (pt.name->>'en_US'), count(*), string_agg(pp.id::text, ',' ORDER BY pp.id)
      FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id
     WHERE pt.active GROUP BY 1 HAVING count(*) > 1 ORDER BY 1
""")
kembar = cr.fetchall()
for nama, n, ids in kembar:
    say("   D1. nama kembar x%d : %-52s pp=%s" % (n, (nama or "")[:52], ids))
say("        → %d kelompok nama kembar (bisa wajar: variasi nama sama antar varian)" % len(kembar))
say("")
cr.execute("""
    WITH fp AS (
      SELECT b.product_tmpl_id, string_agg(l.product_id::text || ':' ||
             ROUND(l.product_qty::numeric,4)::text, '|' ORDER BY l.product_id, ROUND(l.product_qty::numeric,4)) AS sig
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
       WHERE b.active GROUP BY 1)
    SELECT string_agg((pt.name->>'en_US'), '  ||  ' ORDER BY pt.name->>'en_US'), count(*)
      FROM fp JOIN product_template pt ON pt.id=fp.product_tmpl_id
     GROUP BY fp.sig HAVING count(*) > 1 ORDER BY 2 DESC
""")
resep_kembar = cr.fetchall()
for nama, n in resep_kembar:
    say("   D2. resep identik x%d : %s" % (n, nama))
say("        → %d kelompok resep identik" % len(resep_kembar))

# =====================================================================
say("")
say("[5] MARGIN MENU (list_price vs HPP dari resep/ harga beli)")
say("")
HPP = {}
for r in pos_rows:
    cr.execute("""
        SELECT COALESCE(SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric,0)),0)
          FROM mrp_bom_line l JOIN mrp_bom b ON b.id=l.bom_id
          JOIN product_product cp ON cp.id=l.product_id
          JOIN product_template ct ON ct.id=cp.product_tmpl_id
         WHERE b.product_tmpl_id=%s AND b.active
    """, (r["tmpl"],))
    hpp = float(cr.fetchone()[0] or 0)
    if hpp == 0:
        cr.execute("SELECT COALESCE((standard_price->>'1')::numeric,0) FROM product_product WHERE id=%s",
                   (r["pp"],))
        hpp = float(cr.fetchone()[0] or 0)
    HPP[r["tmpl"]] = hpp

rendah = []
for r in pos_rows:
    hpp = HPP[r["tmpl"]]
    px = m_norm.get(r["tmpl"], [(r["list"], "", 0)])[0][0]
    m = (1 - hpp / px) * 100 if px else 0
    if px > 0 and m < TARGET:
        rendah.append((r, px, hpp, m))
rendah.sort(key=lambda x: x[3])
say("   margin < %.0f%% : %d produk POS" % (TARGET, len(rendah)))
say("   %-48s %10s %12s %8s" % ("menu", "jual", "HPP", "margin"))
for r, px, hpp, m in rendah:
    say("   %-48s %10s %12s %7.1f%%" % (r["nama"][:48], money(px), money(hpp), m))

# =====================================================================
say("")
say("[6] RINGKASAN ANOMALI")
say("")
sisa_dua_bom = [r for r in pos_rows if r["tmpl"] not in boms and r["categ"] != "Services"]
checks = [
    ("harga: POS tanpa item pricelist Normal", len(a_missing_norm)),
    ("harga: POS tanpa item pricelist Platform", len(a_missing_plat)),
    ("harga: list_price != Normal", len(a_drift)),
    ("harga: platform tidak = normal+10%% (ceil 500)", len(a_plat_bad)),
    ("harga: item pricelist yatim", len(orphan_items)),
    ("harga: duplikat item pricelist", len(dups)),
    ("harga: POS harga <= 100 (non-Services)", len(cheap)),
    ("BOM: POS tanpa BOM (non-Services)", len(sisa_dua_bom)),
    ("BOM: produk >1 BOM", len(multi)),
    ("BOM: BOM tanpa baris", len(nol)),
    ("BOM: BOM template non-POS/arsip", len(yatim_bom)),
    ("BOM: header UOM != UOM produk", len(uom_beda)),
    ("BOM: baris qty <= 0", len(qty0)),
    ("BOM: komponen berupa produk POS", len(datar)),
    ("BOM: UOM baris != UOM komponen", len(uom_line)),
    ("biaya: komponen tanpa harga", len(zero)),
    ("produk: nama kembar", len(kembar)),
    ("BOM: kelompok resep identik", len(resep_kembar)),
    ("margin: menu < %.0f%%" % TARGET, len(rendah)),
]
for label, n in checks:
    say("   %-46s : %s" % (label, n))
say(SEP)
cr.rollback()
