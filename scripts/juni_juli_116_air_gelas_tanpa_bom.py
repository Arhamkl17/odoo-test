# -*- coding: utf-8 -*-
"""
juni_juli_116_air_gelas_tanpa_bom.py — AIR GELAS TANPA BOM (13 Sep 2026).

KEPUTUSAN PEMILIK (13 Sep 2026):
  • `AIR GELAS` = **barang jual-langsung** (contoh: minuman Sprite) — bukan racikan.
    Jadi BOM yang dibuat skrip 114 (`AIR GALON 200 MIL`) **DIHAPUS**.
    Biayanya diambil dari harga beli (`standard_price` = Rp 500).
  • UOM tetap **PCS** (Odoo tidak mengizinkan ubah karena 28 baris jurnal ter-post).
  • `KEMASAN VARIAN AYAM` / `KEMASAN VARIAN INDOMIE` tetap **PORSI**.

Konteks:
  • `AIR GELAS` (tmpl 641 / pp 630) dipakai sebagai komponen oleh 6 paket:
    BIG HEMAT 1/2/3 & YUKSSS RAMA 1/2/3 (1 PCS). Paket-paket itu mengambil biaya dari
    `standard_price` AIR GELAS, bukan dari BOM-nya — jadi penghapusan ini **tidak**
    mengubah HPP paket tersebut.
  • Pembanding yang benar: `AIR MINERAL BOTOL` (tmpl 648) — punya harga beli, tanpa BOM.

Idempotent. Tidak menyentuh harga jual, stok, dan order historis.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_116_air_gelas_tanpa_bom.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_116_air_gelas_tanpa_bom.py
"""
import os

RUN = os.environ.get("RUN") == "1"
TM = 641          # AIR GELAS

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]
UOM = env["uom.uom"]

say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))


def hpp_of(tmpl_id):
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id=b.id
          LEFT JOIN product_product cp ON cp.id=bl.product_id
         WHERE b.product_tmpl_id = %s
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


def std_price(pp_id):
    cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (pp_id,))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


say("=" * 112)
say("AIR GELAS TANPA BOM (barang jual-langsung)   |   RUN=%s" % RUN)
say("=" * 112)

# ================================================================ GUARD
t = PT.browse(TM)
if not t.exists() or t.name.strip().upper() != "AIR GELAS":
    raise SystemExit("!! tmpl %s bukan AIR GELAS — hentikan.")
pp = t.product_variant_id
boms = BOM.search([("product_tmpl_id", "=", TM)])

say("")
say("[KONDISI SEKARANG]")
say("   AIR GELAS  tmpl=%s pp=%s  kategori=%s  uom=%s  harga jual=%s  harga beli=%s" % (
    t.id, pp.id, t.categ_id.name, t.uom_id.name, money(t.list_price), money(std_price(pp.id))))
say("   BOM        : %d" % len(boms))
for b in boms:
    for l in b.bom_line_ids:
        say("      %-28s %8s %s" % (l.product_id.display_name, l.product_qty,
                                    l.product_uom_id.name))

# dipakai sebagai komponen di mana  (id penerima diambil dinamis, bukan hardcode)
users = env["mrp.bom.line"].search([("product_id", "=", pp.id)])
PEMAKAI = sorted({l.bom_id.product_tmpl_id.id for l in users})
say("   dipakai sebagai komponen oleh %d resep:" % len(users))
for l in users:
    say("      %-46s %s %s" % (l.bom_id.product_tmpl_id.display_name[:46],
                               l.product_qty, l.product_uom_id.name))

# dokumen yang menempel
bad = []
for tbl, col in (("pos_order_line", "product_id"), ("stock_move", "product_id"),
                 ("stock_move_line", "product_id"), ("account_move_line", "product_id")):
    cr.execute("SELECT COUNT(*) FROM %s WHERE %s = %%s" % (tbl, col), (pp.id,))
    bad.append((tbl, cr.fetchone()[0]))
say("   dokumen menempel: %s" % ", ".join("%s=%d" % (a, b) for a, b in bad))
say("      (dokumen ini TIDAK dihapus — penghapusan BOM tidak menyentuhnya)")

if not boms:
    say("")
    say("   → sudah tidak punya BOM (idempotent). Tidak ada yang dikerjakan.")
    say("=" * 112)
    env.cr.rollback()
    raise SystemExit(0)

# ================================================================ RENCANA
say("")
say("[RENCANA]")
say("   Hapus %d BOM milik AIR GELAS beserta barisnya." % len(boms))
say("")
say("   HPP sebelum → sesudah:")
say("      %-30s %12s → %12s   (harga beli)" % (
    "AIR GELAS", money(hpp_of(TM)), money(std_price(pp.id))))
say("")
say("   HPP paket pemakai (memakai harga beli AIR GELAS, bukan BOM-nya):")
for tid in PEMAKAI:
    pt = PT.browse(tid)
    say("      %-30s %14s → %14s" % (pt.display_name[:30], money(hpp_of(tid)), money(hpp_of(tid))))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 112)
    env.cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
hpp_before = hpp_of(TM)
say("")
say("[EKSEKUSI]")
n_line = sum(len(b.bom_line_ids) for b in boms)
for b in boms:
    say("   hapus BOM id=%s (%d baris)" % (b.id, len(b.bom_line_ids)))
boms.unlink()
env.cr.flush()
env.cr.commit()
say("   [COMMITTED]")

# ================================================================ VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
say("")
say("   BOM AIR GELAS sekarang : %d" % BOM.search_count([("product_tmpl_id", "=", TM)]))
say("   HPP dari resep         : %s → %s  (kini 0 karena TIDAK ada resep lagi)" % (
    money(hpp_before), money(hpp_of(TM))))
say("   biaya yang berlaku     : harga beli (standard_price) = %s  ← inilah HPP AIR GELAS sekarang"
    % money(std_price(pp.id)))
say("   catatan: setelah tanpa BOM, biaya produk diambil dari standard_price, bukan resep.")
say("")
cr.execute("""
    SELECT count(*) FROM product_template t
     WHERE t.available_in_pos AND t.active AND t.sale_ok
       AND NOT EXISTS (SELECT 1 FROM mrp_bom b WHERE b.product_tmpl_id=t.id)
""")
say("   produk POS tanpa BOM   : %d" % cr.fetchone()[0])
cr.execute("""
    SELECT (t.name->>'en_US') FROM product_template t
     WHERE t.available_in_pos AND t.active AND t.sale_ok
       AND NOT EXISTS (SELECT 1 FROM mrp_bom b WHERE b.product_tmpl_id=t.id)
     ORDER BY 1
""")
for (nama,) in cr.fetchall():
    say("      - %s" % nama)
say("")
say("   total BOM              : %d" % BOM.search_count([]))
say("")
say("   paket pemakai tetap utuh:")
for tid in PEMAKAI:
    pt = PT.browse(tid)
    say("      %-30s HPP %14s | baris resep %d" % (
        pt.display_name[:30], money(hpp_of(tid)),
        env["mrp.bom.line"].search_count([("product_id", "=", pp.id),
                                          ("bom_id.product_tmpl_id", "=", tid)])))
say("=" * 112)
