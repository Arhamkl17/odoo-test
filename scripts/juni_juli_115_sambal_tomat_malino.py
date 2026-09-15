# -*- coding: utf-8 -*-
"""
juni_juli_115_sambal_tomat_malino.py — BERESKAN SAMBAL TOMAT MALINO (13 Sep 2026).

MASALAH
  Sistem punya 3 bahan sambal di kategori `Bahan Baku Food` (UOM GRM):
      SAMBAL IJO PADANG (651) · SAMBAL KOREK SURABAYA (652) · SAMBAL RICA MANADO (650)
  Tapi `SAMBAL TOMAT MALINO` TIDAK punya bahan — yang ada hanya produk **menu**
  (tmpl 552 / pp 541, Menu Food, PORSI, dijual di POS Rp 6.500). Akibatnya produk
  menu itu dipakai sebagai KOMPONEN oleh dua resep:
      • bom 80  PKG SAMBAL TOMAT MALINO (GEPREK SAMBAL + NASI)  23,29 PORSI
      • bom 92  GEPREK SAMBAL TOMAT MALINO                      23,29 PORSI
  Bandingkan dengan RICA yang benar: `MENU SAMBAL RICA MANADO` (639) memakai
  bahan `SAMBAL RICA MANADO` 23,29 **GRM** + MINYAK GORENG 11,70 MIL.

YANG DILAKUKAN
  A. Buat produk bahan baru `SAMBAL TOMAT MALINO` (Bahan Baku Food, GRM) —
     identik polanya dengan bahan sambal lain (lihat catatan harga di bawah).
  B. Beri BOM untuk produk menu `SAMBAL TOMAT MALINO` (552):
     bahan SAMBAL TOMAT MALINO 23,29 GRM + MINYAK GORENG 11,70 MIL
     (meniru `MENU SAMBAL RICA MANADO` 639).
  C. Alihkan komponen kedua resep (bom 80 & 92) dari produk menu 552 → bahan baru,
     dan ubah UOM barisnya PORSI → GRM.

CATATAN HARGA (penting)
  Belum ada harga beli untuk sambal tomat malino — ini sudah tercatat sebagai
  pertanyaan terbuka ke klien ("SAMBAL TOMAT MALINO tercatat Rp 0 di sistem;
  berapa harga sebenarnya?"). Karena itu `standard_price` bahan baru = 0, sehingga
  **HPP tidak berubah** dibanding sebelum perbaikan. Begitu harga asli masuk,
  jalankan ulang:  RUN=1 HARGA=<rupiah per gram> ...

Idempotent. Tidak menyentuh harga jual & order historis.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_115_sambal_tomat_malino.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_115_sambal_tomat_malino.py
"""
import os

RUN = os.environ.get("RUN") == "1"
HARGA = float(os.environ.get("HARGA", "0"))   # Rp per GRM untuk bahan baru

NAMA = "SAMBAL TOMAT MALINO"
MENU_TMPL = 552        # produk menu (POS) yang salah dipakai sebagai bahan
MENU_PROD = 541        # product.product pasangan MENU_TMPL
PEMBANDING = 650       # SAMBAL RICA MANADO (bahan, GRM) — acuan pola
MINYAK_TMPL = 470      # MINYAK GORENG
QTY_SAMBAL = 23.29     # GRM — sama dengan resep RICA
QTY_MINYAK = 11.70     # MIL — sama dengan resep RICA

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
BOM = env["mrp.bom"]
BOML = env["mrp.bom.line"]
UOM = env["uom.uom"]
PC = env["product.category"]
AML = env["account.move.line"]

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


say("=" * 112)
say("BERESKAN SAMBAL TOMAT MALINO   |   RUN=%s   |   HARGA=%s /GRM" % (RUN, money(HARGA)))
say("=" * 112)

# ================================================================ GUARD
say("")
say("[GUARD]")
menu = PT.browse(MENU_TMPL)
if not menu.exists() or menu.name.strip().upper() != NAMA:
    raise SystemExit("!! tmpl %s bukan %r — hentikan." % (MENU_TMPL, NAMA))

kat_bahan = PC.search([("name", "=", "Bahan Baku Food")], limit=1)
uom_grm = UOM.search([("name", "=", "GRM")], limit=1)
if not kat_bahan or not uom_grm:
    raise SystemExit("!! kategori 'Bahan Baku Food' / UOM 'GRM' tidak ada — hentikan.")

pembanding = PT.browse(PEMBANDING)
if not pembanding.exists():
    raise SystemExit("!! bahan pembanding (SAMBAL RICA MANADO) tidak ada — hentikan.")

bahan_lama = PT.with_context(active_test=False).search([
    ("name", "=", NAMA), ("categ_id", "=", kat_bahan.id)], limit=1)

say("   produk menu  : tmpl=%s pp=%s kategori=%s uom=%s | BOM=%d" % (
    menu.id, MENU_PROD, menu.categ_id.name, menu.uom_id.name,
    BOM.search_count([("product_tmpl_id", "=", menu.id)])))
say("   bahan        : %s" % (
    "sudah ada tmpl=%s" % bahan_lama.id if bahan_lama else "BELUM ADA → akan dibuat"))

# baris resep yang masih menunjuk produk menu 552
lines = BOML.search([("product_id", "=", MENU_PROD)])
say("   resep yang memakai produk menu sbg komponen: %d" % len(lines))
for l in lines:
    say("      bom=%-4s %-46s qty=%s %s" % (
        l.bom_id.id, l.bom_id.product_tmpl_id.display_name[:46],
        l.product_qty, l.product_uom_id.name))
if not lines and bahan_lama:
    say("   → sudah dialihkan sebelumnya (idempotent)")

# ================================================================ RENCANA
say("")
say("[RENCANA]")
say("   A. buat bahan 'SAMBAL TOMAT MALINO' — kategori Bahan Baku Food, UOM GRM,")
say("      purchase_ok=True, sale_ok=True, available_in_pos=False, list_price=1,")
say("      standard_price=%s (pola sama dengan tmpl %s '%s')" % (
    money(HARGA), pembanding.id, pembanding.display_name))
say("   B. BOM tuk produk menu %s (tmpl %s):" % (NAMA, MENU_TMPL))
say("        bahan SAMBAL TOMAT MALINO  %s GRM" % QTY_SAMBAL)
say("        MINYAK GORENG              %s MIL   (acuan: MENU SAMBAL RICA MANADO 639)" % QTY_MINYAK)
say("   C. alihkan %d baris resep: product_id %s → bahan baru, UOM PORSI → GRM" % (
    len(lines), MENU_PROD))

say("")
say("   HPP sebelum → sesudah (dari standard_price komponen):")
for tid, label in ((MENU_TMPL, "SAMBAL TOMAT MALINO (menu)"),
                   (569, "PKG SAMBAL TOMAT MALINO"),
                   (574, "GEPREK SAMBAL TOMAT MALINO")):
    say("      %-30s %14s" % (label, money(hpp_of(tid))))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 112)
    env.cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
hpp_before = {tid: hpp_of(tid) for tid in (MENU_TMPL, 569, 574)}

say("")
say("[EKSEKUSI]")
say("")
say("A. buat bahan")
if bahan_lama:
    bahan = bahan_lama
    if HARGA:
        bahan.product_variant_id.write({"standard_price": HARGA})
    say("   sudah ada: tmpl=%s pp=%s (standard_price=%s)" % (
        bahan.id, bahan.product_variant_id.id, money(bahan.standard_price)))
else:
    bahan = PT.create({
        "name": NAMA,
        "type": "consu",
        "is_storable": True,
        "tracking": "none",
        "categ_id": kat_bahan.id,
        "uom_id": uom_grm.id,
        "sale_ok": True,
        "purchase_ok": True,
        "available_in_pos": False,
        "list_price": 1.0,
    })
    if HARGA:
        bahan.product_variant_id.write({"standard_price": HARGA})
    say("   dibuat: tmpl=%s pp=%s uom=%s kategori=%s" % (
        bahan.id, bahan.product_variant_id.id, bahan.uom_id.name, bahan.categ_id.name))
env.cr.flush()

bahan_prod = bahan.product_variant_id
say("")
say("B. BOM untuk produk menu %s" % NAMA)
if BOM.search_count([("product_tmpl_id", "=", MENU_TMPL)]):
    say("   sudah punya BOM — dilewati")
else:
    bom = BOM.create({
        "product_tmpl_id": MENU_TMPL,
        "product_qty": 1.0,
        "product_uom_id": menu.uom_id.id,
        "type": "phantom",
        "company_id": env.company.id,
        "consumption": "warning",
    })
    minyak = PP.search([("product_tmpl_id", "=", MINYAK_TMPL)], limit=1)
    bom.write({"bom_line_ids": [
        (0, 0, {"product_id": bahan_prod.id, "product_qty": QTY_SAMBAL,
                "product_uom_id": uom_grm.id}),
        (0, 0, {"product_id": minyak.id, "product_qty": QTY_MINYAK,
                "product_uom_id": minyak.uom_id.id}),
    ]})
    say("   BOM dibuat: %s" % bom.display_name)
env.cr.flush()

say("")
say("C. alihkan baris resep")
n_moved = 0
for l in BOML.search([("product_id", "=", MENU_PROD)]):
    say("   bom=%-4s %-46s %s %s → %s %s" % (
        l.bom_id.id, l.bom_id.product_tmpl_id.display_name[:46],
        l.product_qty, l.product_uom_id.name, l.product_qty, "GRM"))
    l.write({"product_id": bahan_prod.id, "product_uom_id": uom_grm.id})
    n_moved += 1
say("   dialihkan: %d baris" % n_moved)

env.cr.flush()
env.cr.commit()
say("")
say("[COMMITTED]")

# ================================================================ VERIFIKASI
say("")
say("=" * 112)
say("[VERIFIKASI]")
say("")
say("   produk bahan baru:")
b = PT.browse(bahan.id)
say("      tmpl=%-5s pp=%-5s %-24s kategori=%-16s uom=%-5s purchase=%s sale=%s POS=%s" % (
    b.id, b.product_variant_id.id, b.display_name, b.categ_id.name, b.uom_id.name,
    b.purchase_ok, b.sale_ok, b.available_in_pos))

say("")
say("   resep yang sekarang memakai bahan baru:")
cr.execute("""
    SELECT b.id, (bt.name->>'en_US'), l.product_qty, (u.name->>'en_US')
      FROM mrp_bom_line l JOIN mrp_bom b ON b.id=l.bom_id
      JOIN product_template bt ON bt.id=b.product_tmpl_id
      LEFT JOIN uom_uom u ON u.id=l.product_uom_id
     WHERE l.product_id = %s ORDER BY b.id
""", (bahan_prod.id,))
for bid, pemakai, qty, un in cr.fetchall():
    say("      bom=%-4s %-46s %s %s" % (bid, (pemakai or "")[:46], qty, un))

say("")
say("   BOM produk menu %s:" % NAMA)
cr.execute("""
    SELECT (ct.name->>'en_US'), l.product_qty, (u.name->>'en_US')
      FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
      JOIN product_product cp ON cp.id=l.product_id
      JOIN product_template ct ON ct.id=cp.product_tmpl_id
      LEFT JOIN uom_uom u ON u.id=l.product_uom_id
     WHERE b.product_tmpl_id = %s ORDER BY 1
""", (MENU_TMPL,))
for komp, qty, un in cr.fetchall():
    say("      %-28s %8s %s" % (komp, qty, un))

say("")
say("   HPP sebelum → sesudah:")
for tid, label in ((MENU_TMPL, "SAMBAL TOMAT MALINO (menu)"),
                   (569, "PKG SAMBAL TOMAT MALINO"),
                   (574, "GEPREK SAMBAL TOMAT MALINO")):
    say("      %-30s %14s → %14s  %s" % (
        label, money(hpp_before[tid]), money(hpp_of(tid)),
        "sama" if abs(hpp_of(tid) - hpp_before[tid]) < 0.01 else "BERUBAH"))
say("")
say("   sisa produk POS tanpa BOM: %d" % PT.search_count([
    ("available_in_pos", "=", True), ("sale_ok", "=", True),
    ("id", "not in", BOM.search([]).product_tmpl_id.ids)]))
say("=" * 112)
