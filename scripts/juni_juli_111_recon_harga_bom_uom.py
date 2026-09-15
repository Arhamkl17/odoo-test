# -*- coding: utf-8 -*-
"""
juni_juli_111_recon_harga_bom_uom.py — REKON READ-ONLY (13 Sep 2026).

Tujuan: memotret kondisi harga jual / BOM / UOM / preset POS SEBELUM
penyatuan harga dijalankan. Tidak menulis apa pun.

  jalan: su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
         --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
         < scripts/juni_juli_111_recon_harga_bom_uom.py
"""
import collections
import datetime
import os

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
PL = env["product.pricelist"]
PLI = env["product.pricelist.item"]
CFG = env["pos.config"]
PRE = env["pos.preset"]
BOM = env["mrp.bom"]

say = lambda m="": print(m)
money = lambda x: "{:,.0f}".format(float(x or 0))

# ---------------------------------------------------------------- util
def item_map(pl):
    """{product_tmpl_id: fixed_price} untuk satu pricelist."""
    out = {}
    if not pl:
        return out
    for it in PLI.search([("pricelist_id", "=", pl.id)]):
        if it.product_tmpl_id:
            out[it.product_tmpl_id.id] = float(it.fixed_price or 0)
    return out


def bom_lines(tmpl_id):
    boms = BOM.search([("product_tmpl_id", "=", tmpl_id)])
    n = 0
    for b in boms:
        n += len(b.bom_line_ids)
    return len(boms), n


pl3 = PL.search([("id", "=", 3)], limit=1)
# pricelist 4 sudah diarsipkan → wajib active_test=False
pl4 = PL.with_context(active_test=False).search([("name", "=", "Harga Dine In")], limit=1)
m3, m4 = item_map(pl3), item_map(pl4)

prods = PP.search([("available_in_pos", "=", True), ("sale_ok", "=", True)])
rows = []
for p in prods:
    t = p.product_tmpl_id
    nbom, nline = bom_lines(t.id)
    rows.append({
        "pp": p.id, "tmpl": t.id, "nama": t.display_name,
        "list": float(t.list_price or 0),
        "pl3": m3.get(t.id), "pl4": m4.get(t.id),
        "uom": t.uom_id.display_name if t.uom_id else "(TANPA UOM)",
        "categ": t.categ_id.name if t.categ_id else "(TANPA KATEGORI)",
        "nbom": nbom, "nline": nline,
    })

# ================================================================ 1
say("=" * 122)
say("REKON HARGA · BOM · UOM  |  %s  |  read-only" % datetime.date.today().isoformat())
say("=" * 122)

say("")
say("[1] DAFTAR HARGA, POS CONFIG & PRESET")
say("")
say("  pricelist:")
for pl in PL.with_context(active_test=False).search([]):
    n = PLI.search_count([("pricelist_id", "=", pl.id)])
    say("     id=%-3s %-34s aktif=%-5s item=%d" % (pl.id, pl.name, pl.active, n))

say("")
say("  pos.config:")
for c in CFG.with_context(active_test=False).search([]):
    say("     id=%-3s %-24s aktif=%-5s pricelist=%-30s use_pricelist=%-5s "
        "preset(default=%s, n=%d)" % (
            c.id, c.name, c.active,
            c.pricelist_id.name or "(kosong)",
            bool(c.use_pricelist), c.default_preset_id.name or "-",
            len(c.available_preset_ids)))

say("")
say("  pos.preset:")
for pr in PRE.search([]):
    say("     id=%-3s %-12s pricelist=%-24s dipakai config=%s" % (
        pr.id, pr.name, pr.pricelist_id.name or "(KOSONG)",
        pr.sudo().count_linked_config))

# ================================================================ 2
say("")
say("[2] HARGA PER PRODUK POS   (list_price vs pricelist 3 vs pricelist 4)")
say("")
say("  %-4s %-50s %10s %10s %10s %-6s %-12s %s" % (
    "pp", "produk", "list", "pl3", "pl4/dinein", "uom", "kategori", "bom"))
say("  " + "-" * 118)
for r in sorted(rows, key=lambda x: -x["list"]):
    say("  %-4s %-50s %10s %10s %10s %-6s %-12s %s" % (
        r["pp"], r["nama"][:50], money(r["list"]),
        money(r["pl3"]) if r["pl3"] is not None else "—",
        money(r["pl4"]) if r["pl4"] is not None else "—",
        r["uom"][:6], r["categ"][:12],
        ("%d bom/%d baris" % (r["nbom"], r["nline"]))))
say("  total produk POS: %d" % len(rows))

# ================================================================ 3
say("")
say("[3] ANOMALI UOM")
say("")
dist = collections.Counter(r["uom"] for r in rows)
say("  sebaran UOM produk POS: %s" % ", ".join(
    "%s=%d" % (k, v) for k, v in dist.most_common()))
say("")
say("  a) `Menu Food` yang BUKAN PORSI/PAKET:")
food_bad = [r for r in rows if r["categ"] == "Menu Food"
            and r["uom"] not in ("PORSI", "PAKET", "PTG")]
for r in sorted(food_bad, key=lambda x: (x["uom"], x["nama"])):
    say("       %-50s uom=%s" % (r["nama"][:50], r["uom"]))
say("       → %d produk" % len(food_bad))
say("")
say("  b) `Menu Beverage` yang BUKAN GELAS:")
bev_bad = [r for r in rows if r["categ"] == "Menu Beverage" and r["uom"] != "GELAS"]
for r in bev_bad:
    say("       %-50s uom=%s" % (r["nama"][:50], r["uom"]))
say("       → %d produk" % len(bev_bad))
say("")
say("  c) produk POS TANPA KATEGORI PRODUK:")
no_cat = [r for r in rows if r["categ"] == "(TANPA KATEGORI)"]
for r in sorted(no_cat, key=lambda x: x["nama"]):
    say("       %-50s uom=%-6s %10s" % (r["nama"][:50], r["uom"], money(r["list"])))
say("       → %d produk" % len(no_cat))
say("")
say("  d) UOM non-standar lain di luar Menu Food/Beverage:")
lain = [r for r in rows if r["categ"] not in ("Menu Food", "Menu Beverage", "(TANPA KATEGORI)")]
for r in sorted(lain, key=lambda x: x["nama"]):
    say("       %-50s uom=%-6s kategori=%s" % (r["nama"][:50], r["uom"], r["categ"]))

# ================================================================ 4
say("")
say("[4] ANOMALI BOM")
say("")
say("  a) produk POS TANPA BOM:")
no_bom = [r for r in rows if r["nbom"] == 0]
for r in sorted(no_bom, key=lambda x: (-x["list"], x["nama"])):
    say("       %-50s %-12s %10s" % (r["nama"][:50], r["categ"][:12], money(r["list"])))
say("       → %d produk" % len(no_bom))
say("")
say("  b) produk POS dengan LEBIH DARI SATU BOM:")
multi = [r for r in rows if r["nbom"] > 1]
for r in multi:
    say("       %-50s %d bom" % (r["nama"][:50], r["nbom"]))
say("       → %d produk" % len(multi))
say("")
say("  c) BOM yang menunjuk produk non-aktif / produk tanpa harga:")
cr.execute("""
    SELECT DISTINCT (bt.name->>'en_US'), (ct.name->>'en_US')
      FROM mrp_bom b
      JOIN mrp_bom_line l ON l.bom_id=b.id
      JOIN product_product cp ON cp.id=l.product_id
      JOIN product_template ct ON ct.id=cp.product_tmpl_id
      JOIN product_template bt ON bt.id=b.product_tmpl_id
     WHERE ct.active = false
     ORDER BY 2
""")
bad_comp = cr.fetchall()
for bt, ct in bad_comp[:20]:
    say("       %-44s → komponen non-aktif: %s" % ((bt or "")[:44], ct))
say("       → %d baris" % len(bad_comp))

# ================================================================ 5
say("")
say("[5] BOM SISTEM vs BERKAS MASTER (data sheet master)")
say("")
DIR = "product_photos/data sheet master"
MASTER = [
    ("mrp_bom FIX - PALLANGGA.xlsx", "Template"),
    ("mrp_bom Barang Combo.xlsx", "FIX BOM GANTI COMBO"),
]
try:
    import openpyxl

    master = collections.OrderedDict()
    for fn, sheet in MASTER:
        path = os.path.join(DIR, fn)
        if not os.path.exists(path):
            say("  ⚠ berkas tidak ada: %s" % path)
            continue
        n_before = len(master)
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[sheet]
        got = list(ws.iter_rows(values_only=True))
        hdr = [str(c).strip() if c is not None else "" for c in got[0]]
        cur = None
        for r in got[1:]:
            d = {hdr[i]: (r[i] if i < len(r) else None) for i in range(len(hdr))}
            nm = d.get("Produk")
            if nm not in (None, ""):
                cur = str(nm).strip()
            comp = d.get("Baris BoM/Komponen")
            if cur and comp not in (None, ""):
                master.setdefault(cur, []).append(
                    (str(comp).strip(), round(float(d.get("Baris BoM/Kuantitas") or 0), 4)))
        wb.close()
        say("  %-34s sheet %-22s %d produk" % (fn, sheet, len(master) - n_before))

    # BOM sistem per nama produk
    cr.execute("""
        SELECT (bt.name->>'en_US') AS produk, (ct.name->>'en_US') AS komponen,
               ROUND(l.product_qty::numeric, 4) AS qty
          FROM mrp_bom b
          JOIN product_template bt ON bt.id=b.product_tmpl_id
          JOIN mrp_bom_line l ON l.bom_id=b.id
          JOIN product_product cp ON cp.id=l.product_id
          JOIN product_template ct ON ct.id=cp.product_tmpl_id
         ORDER BY 1, 2
    """)
    sysb = collections.defaultdict(list)
    for p, c, q in cr.fetchall():
        sysb[p].append((c, float(q)))

    hanya_master = sorted(set(master) - set(sysb))
    hanya_sistem = sorted(set(sysb) - set(master))
    beda = [k for k in (set(master) & set(sysb))
            if sorted(master[k]) != sorted(sysb[k])]

    say("")
    say("  produk master %d | produk dengan BOM di sistem %d" % (len(master), len(sysb)))
    say("  • ada di master, TIDAK ada BOM di sistem : %d" % len(hanya_master))
    for k in hanya_master:
        say("       %s" % k)
    say("  • ada BOM di sistem, TIDAK ada di master : %d" % len(hanya_sistem))
    for k in hanya_sistem[:40]:
        say("       %-52s (%d baris)" % (k, len(sysb[k])))
    say("  • isi BEDA (qty berbeda)                  : %d" % len(beda))
    for k in beda[:15]:
        sa, sb = set(master[k]), set(sysb[k])
        say("       %-46s master-only=%s | sistem-only=%s" % (
            k[:46], sorted(sa - sb)[:3], sorted(sb - sa)[:3]))
except ImportError:
    say("  (openpyxl tidak tersedia di lingkungan ini — bagian ini dilewati)")

# ================================================================ 6
say("")
say("[6] RINGKASAN")
say("")
say("  produk POS            : %d" % len(rows))
say("  punya item pricelist 3: %d" % len([r for r in rows if r["pl3"] is not None]))
say("  punya item pricelist 4: %d" % len([r for r in rows if r["pl4"] is not None]))
say("  tanpa item pricelist  : %s" % ", ".join(
    "%s (pp %s)" % (r["nama"], r["pp"]) for r in rows if r["pl3"] is None) or "-")
say("  tanpa BOM             : %d produk" % len(no_bom))
say("  lebih dari 1 BOM      : %d produk" % len(multi))
say("  UOM menu food anomali : %d produk" % len(food_bad))
say("  tanpa kategori produk : %d produk" % len(no_cat))
say("")
say("  Rencana (lihat skrip 112): satu harga = kolom pl4/dine-in; "
    "pricelist platform = +10%% dibulatkan Rp 500; preset Dine In/Takeout/Delivery.")
say("=" * 122)
