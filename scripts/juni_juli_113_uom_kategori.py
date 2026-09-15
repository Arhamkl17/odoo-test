# -*- coding: utf-8 -*-
"""
juni_juli_113_uom_kategori.py — SERAGAMKAN UOM + ISI KATEGORI PRODUK (13 Sep 2026).

Latar (temuan skrip 111):
  • 41 produk `Menu Food` memakai UOM `Units` (campur dengan PORSI/PAKET).
  •  9 add-on POS tidak punya kategori produk (`categ_id = False`).
  •  `AIR GELAS` berkategori `Bahan Baku Beverage` dengan UOM `PCS`.

Aturan UOM (bertingkat, TIDAK menebak):
  1. **Acuan utama**: `import_data/csv/04_products_menu.csv` — daftar Unit dari KLIEN.
     Semua 47 produk yang sudah PORSI/PAKET terbukti cocok 100% dengan berkas ini.
  2. Produk yang tidak ada di berkas klien (keluarga ekspor kedua) memakai aturan nama:
       - diawali `PAKET` / `PKG` / `PKC` / `BIG HEMAT` / `YUKSSS RAMA` → **PAKET**
       - `SEGEPOK BERLIMA` → **PAKET**
       - sisanya → **PORSI**
  3. `Menu Beverage` → **GELAS**; kategori `Services` tidak disentuh.

Sekaligus:
  • 9 add-on tanpa kategori → dimasukkan ke `Menu Food`.
  • `AIR GELAS` → kategori `Menu Beverage`, UOM `GELAS`.

Idempotent. Tidak menyentuh harga, BOM, atau order historis.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_113_uom_kategori.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_113_uom_kategori.py
"""
import csv
import os

RUN = os.environ.get("RUN") == "1"
CSV_KLIEN = "import_data/csv/04_products_menu.csv"
KAT_FOOD, KAT_BEV = "Menu Food", "Menu Beverage"
PAKET_PREFIX = ("PAKET", "PKG", "PKC", "BIG HEMAT", "YUKSSS RAMA")
PAKET_KHUSUS = {"SEGEPOK BERLIMA": "PAKET"}
AIR_GELAS = 641   # template AIR GELAS

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]
UOM = env["uom.uom"]
PC = env["product.category"]

say = lambda m="": print(m)


def kategori(t):
    return t.categ_id.name if t.categ_id else None


# ---------------------------------------------------------------- acuan klien
klien = {}
with open(CSV_KLIEN, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        klien.setdefault(r["Nama"].strip().upper(), r["Unit"].strip())


def uom_target(nama, kat):
    """UOM yang dituju: berkas klien dulu, baru aturan nama."""
    if kat == KAT_BEV:
        return "GELAS"
    n = nama.strip().upper()
    if n in klien:
        return klien[n]
    if n in PAKET_KHUSUS:
        return PAKET_KHUSUS[n]
    if n.startswith(PAKET_PREFIX):
        return "PAKET"
    return "PORSI"


uoms = {}
for nm in ("PORSI", "PAKET", "GELAS"):
    u = UOM.search([("name", "=", nm)], limit=1)
    if not u:
        raise SystemExit("!! UOM %r tidak ada — hentikan." % nm)
    uoms[nm] = u
kat_food = PC.search([("name", "=", KAT_FOOD)], limit=1)
kat_bev = PC.search([("name", "=", KAT_BEV)], limit=1)
if not kat_food or not kat_bev:
    raise SystemExit("!! kategori Menu Food / Menu Beverage tidak ada — hentikan.")

prods = PP.search([("available_in_pos", "=", True), ("sale_ok", "=", True)])

# ---------------------------------------------------------------- rencana
# Odoo menolak ubah `uom_id` produk yang sudah dipakai di jurnal ter-post
# (`account._check_uom_not_in_invoice`). Pra-cek supaya skrip tidak gagal di tengah.
AML = env["account.move.line"]
fix_kat, fix_uom, dilewati, terhalang = [], [], [], []
for p in prods:
    t = p.product_tmpl_id
    nama, kat = t.display_name, kategori(t)
    kat_baru = kat
    if kat is None:
        kat_baru = KAT_FOOD
    elif t.id == AIR_GELAS:
        kat_baru = KAT_BEV
    if kat_baru != kat:
        fix_kat.append((t, kat, kat_baru))
    # UOM hanya untuk Menu Food / Menu Beverage (Services dilewati)
    if kat_baru not in (KAT_FOOD, KAT_BEV):
        if t.uom_id.name != "Units":
            dilewati.append((t, kat_baru, t.uom_id.name))
        continue
    target = uom_target(nama, kat_baru)
    if t.uom_id.name != target:
        src = "klien" if nama.strip().upper() in klien else "aturan"
        n_posted = AML.search_count([("product_id", "=", p.id),
                                     ("parent_state", "=", "posted")])
        if n_posted:
            terhalang.append((t, t.uom_id.name, target, n_posted))
        else:
            fix_uom.append((t, t.uom_id.name, target, src))

say("=" * 112)
say("SERAGAMKAN UOM + ISI KATEGORI   |   RUN=%s" % RUN)
say("=" * 112)
say("")
say("   acuan klien (%s): %d nama" % (CSV_KLIEN, len(klien)))
say("   produk POS: %d" % len(prods))
say("")
say("[1] KATEGORI PRODUK  (%d diubah)" % len(fix_kat))
for t, a, b in fix_kat:
    say("   %-46s %s → %s" % (t.display_name[:46], a or "(kosong)", b))
say("")
say("[2] UOM  (%d diubah)" % len(fix_uom))
for t, a, b, src in fix_uom:
    say("   tmpl=%-5s %-46s %-7s → %-7s [%s]" % (t.id, t.display_name[:46], a, b, src))
say("")
say("   dilewati (di luar Menu Food/Beverage): %s" % (
    ", ".join("%s(%s)" % (t.display_name, u) for t, k, u in dilewati) or "-"))
say("")
say("[3] UOM TERHALANG — produk sudah dipakai di jurnal ter-post (%d)" % len(terhalang))
for t, a, b, n in terhalang:
    say("   tmpl=%-5s %-46s %-7s → %-7s  (%d baris jurnal)" % (
        t.id, t.display_name[:46], a, b, n))
if terhalang:
    say("   → Odoo melarang ubah UOM produk berjurnal posted. Pilihan: (a) biarkan,")
    say("     (b) arsipkan produk lalu buat baru (mengubah riwayat). Kategori tetap diubah.")

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 112)
    env.cr.rollback()
    raise SystemExit(0)

# ---------------------------------------------------------------- eksekusi
say("")
say("[EKSEKUSI]")
n_kat = n_uom = 0
for t, _a, b in fix_kat:
    t.write({"categ_id": (kat_bev if b == KAT_BEV else kat_food).id})
    n_kat += 1
for t, _a, b, _s in fix_uom:
    t.write({"uom_id": uoms[b].id})
    n_uom += 1
env.cr.flush()
env.cr.commit()
say("   kategori diubah: %d | UOM diubah: %d" % (n_kat, n_uom))
say("   [COMMITTED]")

# ---------------------------------------------------------------- verifikasi
say("")
say("[VERIFIKASI]")
cr.execute("""
    SELECT COALESCE(pc.name,'(TANPA KATEGORI)') kat, COALESCE(u.name->>'en_US','?') uom, count(*)
      FROM product_template t
      LEFT JOIN product_category pc ON pc.id=t.categ_id
      LEFT JOIN uom_uom u ON u.id=t.uom_id
     WHERE t.available_in_pos AND t.active AND t.sale_ok
     GROUP BY 1,2 ORDER BY 1,3 DESC
""")
say("   %-24s %-8s %s" % ("kategori", "uom", "jumlah"))
for kat, uom, n in cr.fetchall():
    say("   %-24s %-8s %d" % (kat, uom, n))
say("")
say("   produk tanpa kategori : %d" % PT.search_count(
    [("available_in_pos", "=", True), ("sale_ok", "=", True), ("categ_id", "=", False)]))
say("   AIR GELAS             : kategori=%s uom=%s" % (
    kategori(PT.browse(AIR_GELAS)), PT.browse(AIR_GELAS).uom_id.name))
say("=" * 112)
