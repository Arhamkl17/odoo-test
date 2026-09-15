# -*- coding: utf-8 -*-
"""
perbaikan_master_06_harga_bubuk_oranges.py — BUBUK ORANGES 8,33 → 100 /GRM (13 Sep 2026).

MASALAH
  `AUDIT_MASTER_DATA_2026-09-13.md` §8.5 mencatat `BUBUK ORANGES` punya dua harga berbeda
  dari sumber klien. Ternyata **kolom `HRG/SAT KECIL` di berkas klien yang salah hitung.**

BUKTI (dari `HARGA BAHAN BAKU GUDANG.xlsx` baris 'Bubuk Oranges' sendiri)

  | kolom          | isi           |
  |----------------|---------------|
  | Satuan (beli)  | Karton @12Bks |
  | Harga          | 672.000       |
  | Isi            | 6.720 Grm     |
  | HRG/SAT KECIL  | 8,3333   ←--- |
  | Satuan (kecil) | GRM           |

  672.000 ÷ 6.720 g = **100,00 /GRM**. Angka 8,3333 = 672.000 ÷ 6.720 ÷ 12 — kolom itu
  membagi 12 (jumlah bks) PADAHAL "Isi" sudah menyatakan total satu karton (6.720 g =
  12 × 560 g). Jadi rumusnya membagi dua kali.

  Bukti kedua (independen): kolom **`Modal`** di `Produk (product.template) (87).xlsx`
  untuk `BUBUK ORANGES` = **100,0** — cocok dengan 100, bukan 8,33.

  Bukti ketiga (konsistensi berkas): dari 75 baris yang bisa diverifikasi, **68 memenuhi
  `Harga ÷ Isi = HRG/SAT KECIL`**. Yang menyimpang hanya baris ber-pola "Satuan @N…":
  Bubuk Oranges, Alas Nasi Bundar, Plastik Klip 5X8 & 7X10, Plastik Putih Takeaway 15 & 24,
  Roll Cup Press — semuanya kebesaran faktor @N (kecuali Roll Cup Press yang tidak dibagi
  sama sekali). Artinya aturan berkasnya = `Harga ÷ Isi`, dan 7 baris itu salah.

  Sanity check harga: Rp 100.000/kg duduk rapi di antara `LEMON TEA` Rp 70.000/kg dan
  `BUBUK MILO` Rp 114.583/kg. Rp 8.330/kg lebih murah daripada gula — tidak masuk akal.

DAMPAK (hanya 2 menu memakai bahan ini)
  | menu                 | jual    | HPP           | margin        |
  |----------------------|--------:|--------------:|--------------:|
  | ORANGE               |  5.000  | 963,48 → 2.338,53 | 80,7% → 53,2% |
  | PAKET MEVVAH BERDUA  | 53.500  | 28.803,80 → 31.553,90 | 46,2% → 41,0% |

MODE
  default        → hanya `BUBUK ORANGES` yang diubah (bukti ganda, aman).
  SEMUA=1        → sekaligus 5 bahan lain yang kena bug rumus sama. Belum dikonfirmasi
                   klien, impact-nya lebih lebar (ALAS NASI BUNDAR dipakai 70 menu), jadi
                   jalankan hanya bila sudah disetujui.

CATATAN
  Berkas klien `HARGA BAHAN BAKU GUDANG.xlsx` **tidak diubah** oleh skrip ini. Selama kolom
  `HRG/SAT KECIL` baris itu belum dibetulkan di berkasnya, menjalankan ulang
  `juni_juli_117_harga_bahan_klien.py` akan mengembalikan harga yang salah.

  Produk kategori `Bahan Baku Beverage`/`Bahan Baku Food` = `fifo` → menulis `standard_price`
  tidak memicu revaluasi/jurnal. Idempotent. Dry-run penuh.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_06_harga_bubuk_oranges.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_06_harga_bubuk_oranges.py
"""
import os

RUN = os.environ.get("RUN") == "1"
SEMUA = os.environ.get("SEMUA") == "1"
PL_NORMAL = 3

# (nama, jadi, dari_harap, uom, dasar)
UTAMA = [
    ("BUBUK ORANGES", 100.0, 8.329997246696035, "GRM",
     "berkas klien: 672.000 / 6.720 g = 100 (kolom HRG/SAT KECIL salah ÷12); Modal klien = 100"),
]

TAMBAHAN = [   # SEMUA=1 — bug rumus sama, belum dikonfirmasi klien
    ("ALAS NASI BUNDAR",         106.66666666666667, 21.33001134912754, "LEMBAR",
     "80.000 / 750 Lbr = 106,67 (berkas ÷5)"),
    ("PLASTIK KLIP 8X5",         51.0,               5.100002886711025, "LEMBAR",
     "51.000 / 1.000 Lbr = 51 (berkas ÷10)"),
    ("PLASTIK PUTIH TAKEAWAY UK. 15", 224.0,         44.8,              "LEMBAR",
     "56.000 / 250 Lbr = 224 (berkas ÷5)"),
    ("PLASTIK PUTIH TAKEAWAY UK. 24", 229.0,         22.9,              "LEMBAR",
     "114.500 / 500 Lbr = 229 (berkas ÷10)"),
    ("ROLL CUP PRESS",           44.0,               88000.0,           "PCS",
     "88.000 / 2.000 Pcs = 44 (berkas tidak dibagi)"),
]
# Catatan: baris 'Plastik Klip 7X10' di berkas klien tidak ada produknya di DB, jadi
# tidak masuk daftar. Cek ulang kalau nanti produknya dibuat.

cr = env.cr
PP = env["product.product"]
PT = env["product.template"]

say = lambda m="": print(m)
money = lambda x: "{:>12,.2f}".format(float(x or 0))


def hpp_of(tmpl_id):
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


def harga_jual(tmpl_id):
    cr.execute("SELECT fixed_price FROM product_pricelist_item "
               "WHERE pricelist_id=%s AND product_tmpl_id=%s LIMIT 1", (PL_NORMAL, tmpl_id))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


def menu_pemakai(pp_id):
    cr.execute("""SELECT DISTINCT b.product_tmpl_id FROM mrp_bom_line bl
                   JOIN mrp_bom b ON b.id=bl.bom_id WHERE bl.product_id=%s AND b.active""", (pp_id,))
    return [r[0] for r in cr.fetchall()]


# ================================================================ GUARD + RENCANA
say("=" * 116)
say("PERBAIKI HARGA BUBUK ORANGES   |   RUN=%s   |   SEMUA=%s   |   %s" % (
    RUN, SEMUA, "TULIS" if RUN else "DRY-RUN"))
say("=" * 116)

TARGET = list(UTAMA) + (list(TAMBAHAN) if SEMUA else [])
if not SEMUA:
    say("")
    say("   mode: HANYA Bubuk Oranges. Jalankan dengan SEMUA=1 untuk sekaligus 5 bahan")
    say("   lain yang kena bug rumus sama (default sengaja tidak, belum dikonfirmasi klien).")

say("")
say("[GUARD]")
rencana, masalah = [], []
for nama, baru, lama_harap, uom, dasar in TARGET:
    hits = PP.with_context(active_test=False).search([("name", "=", nama)])
    if len(hits) != 1:
        masalah.append("%s: %d produk (harus 1)" % (nama, len(hits)))
        continue
    p = hits[0]
    t = p.product_tmpl_id
    uom_aktual = t.uom_id.name or ""
    lama = float(p.standard_price or 0)
    if uom_aktual != uom:
        masalah.append("%s: UoM %r (harap %r) — DILEWATI" % (nama, uom_aktual, uom))
        continue
    if abs(lama - lama_harap) > 0.02:
        masalah.append("%s: harga sekarang %s, diharapkan %s — DILEWATI (DB berubah?)"
                       % (nama, money(lama), money(lama_harap)))
        continue
    if abs(lama - baru) < 1e-9:
        masalah.append("%s: sudah %s — dilewati (idempotent)" % (nama, baru))
        continue
    rencana.append(dict(nama=nama, pp=p, tmpl=t, uom=uom, lama=lama, baru=baru,
                        dasar=dasar, menus=menu_pemakai(p.id)))

say("   bahan siap diubah : %d dari %d" % (len(rencana), len(TARGET)))
for m in masalah:
    say("   !! %s" % m)
if not rencana:
    say("")
    say("   Tidak ada yang perlu dikerjakan — berhenti.")
    say("=" * 116)
    cr.rollback()
    raise SystemExit(0)

say("")
say("   %-30s %-6s %14s %14s %5s  %s" % ("bahan", "UoM", "harga lama", "harga baru", "menu", "dasar"))
say("   " + "-" * 112)
for r in rencana:
    say("   %-30s %-6s %s %s %5d  %s" % (
        r["nama"][:30], r["uom"], money(r["lama"]), money(r["baru"]), len(r["menus"]), r["dasar"][:52]))

# ================================================================ DAMPAK
terdampak = {}
for r in rencana:
    for tid in r["menus"]:
        cr.execute("""SELECT COALESCE(SUM(bl.product_qty),0) FROM mrp_bom_line bl
                       JOIN mrp_bom b ON b.id=bl.bom_id
                      WHERE bl.product_id=%s AND b.product_tmpl_id=%s AND b.active""",
                   (r["pp"].id, tid))
        q = float(cr.fetchone()[0] or 0)
        terdampak.setdefault(tid, []).append((r["nama"], q, q * (r["baru"] - r["lama"])))

say("")
say("[DAMPAK] %d menu memakai bahan yang diubah" % len(terdampak))
say("   %-46s %13s %13s %11s %8s %8s" % ("menu", "HPP lama", "HPP baru", "jual", "margin", "m.baru"))
say("   " + "-" * 108)
hasil = []
for tid, info in terdampak.items():
    t = PT.browse(tid)
    h0 = hpp_of(tid)
    d = sum(x[2] for x in info)
    h1 = h0 + d
    harga = harga_jual(tid)
    hasil.append((t, h0, h1, harga, info, d))
hasil.sort(key=lambda x: -abs(x[5]))
for t, h0, h1, harga, info, d in hasil:
    m0 = (1 - h0 / harga) * 100 if harga else 0
    m1 = (1 - h1 / harga) * 100 if harga else 0
    say("   %-46s %s %s %11s %7.1f%% %7.1f%%" % (
        t.display_name[:46], money(h0), money(h1), money(harga), m0, m1))
say("")
say("   rincian pemakaian:")
for r in rencana:
    for tid in r["menus"]:
        t = PT.browse(tid)
        cr.execute("""SELECT COALESCE(SUM(bl.product_qty),0) FROM mrp_bom_line bl
                       JOIN mrp_bom b ON b.id=bl.bom_id
                      WHERE bl.product_id=%s AND b.product_tmpl_id=%s AND b.active""",
                   (r["pp"].id, tid))
        q = float(cr.fetchone()[0] or 0)
        say("     %-24s di %-30s %8.4g %s  (%+.2f)" % (
            r["nama"][:24], t.display_name[:30], q, r["uom"], q * (r["baru"] - r["lama"])))

# ---- ringkasan margin menu minuman
say("")
say("   cek menu minuman terkait:")
for tid, info in terdampak.items():
    t = PT.browse(tid)
    if t.categ_id.name not in ("Menu Beverage",):
        continue
    h0 = hpp_of(tid); d = sum(x[2] for x in info); h1 = h0 + d
    harga = harga_jual(tid)
    say("     %-30s HPP %s → %s | jual %s | margin %.1f%% → %.1f%%" % (
        t.display_name[:30], money(h0), money(h1), money(harga),
        (1 - h0 / harga) * 100 if harga else 0, (1 - h1 / harga) * 100 if harga else 0))

# ================================================================ DRY-RUN
if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 116)
    cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
say("")
say("[EKSEKUSI] menulis standard_price (produk fifo → tanpa revaluasi/jurnal)")
for r in rencana:
    r["pp"].with_context(disable_auto_revaluation=True).standard_price = r["baru"]
    say("   %-30s %s → %s  (%s)" % (r["nama"][:30], money(r["lama"]), money(r["baru"]), r["uom"]))
cr.flush()
cr.commit()
say("   [COMMITTED] %d bahan" % len(rencana))

# ================================================================ VERIFIKASI
say("")
say("=" * 116)
say("[VERIFIKASI]")
salah = 0
for r in rencana:
    cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (r["pp"].id,))
    kini = float(cr.fetchone()[0] or 0)
    if abs(kini - r["baru"]) > 0.005:
        salah += 1
        say("   !! %s masih %s (seharusnya %s)" % (r["nama"], money(kini), money(r["baru"])))
say("   bahan sesuai target : %d / %d" % (len(rencana) - salah, len(rencana)))

say("")
say("   HPP menu terdampak (sebelum → sesudah):")
for t, h0, h1, harga, info, d in hasil:
    say("     %-46s %s → %s  (%+.2f)  margin %.1f%% → %.1f%%" % (
        t.display_name[:46], money(h0), money(h1), d,
        (1 - h0 / harga) * 100 if harga else 0, (1 - h1 / harga) * 100 if harga else 0))

say("")
say("   sebaran margin menu (semua):")
cr.execute("""
    WITH hpp AS (
      SELECT b.product_tmpl_id tid, SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric,0)) h
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id=b.id
        JOIN product_product cp ON cp.id=l.product_id WHERE b.active GROUP BY 1)
    SELECT COUNT(*), COUNT(*) FILTER (WHERE m < 0),
           COUNT(*) FILTER (WHERE m >= 0 AND m < 30),
           COUNT(*) FILTER (WHERE m >= 30 AND m < 40),
           COUNT(*) FILTER (WHERE m >= 40 AND m < 45),
           COUNT(*) FILTER (WHERE m >= 45),
           ROUND(AVG(m),1), ROUND(AVG(100-m),1)
      FROM (SELECT (1 - COALESCE(hpp.h,(cp.standard_price->>'1')::numeric)/NULLIF(i.fixed_price,0))*100 m
              FROM product_template pt JOIN product_product cp ON cp.product_tmpl_id=pt.id
              JOIN product_pricelist_item i ON i.product_tmpl_id=pt.id AND i.pricelist_id=3
              LEFT JOIN hpp ON hpp.tid=pt.id
             WHERE pt.active AND pt.available_in_pos AND pt.sale_ok AND pt.type<>'service') x
""")
tot, rugi, b30, b40, b45, atas, avg_m, avg_c = cr.fetchone()
say("     total %d | rugi %d | 0-30%% %d | 30-40%% %d | 40-45%% %d | >=45%% %d | rata margin %.1f%% (cost ratio %.1f%%)" % (
    tot, rugi, b30, b40, b45, atas, avg_m, avg_c))

say("")
say("   bahan yang masih menyimpang di berkas klien (belum diubah%s):" % ("" if SEMUA else " — jalankan SEMUA=1"))
for nama, baru, lama_harap, uom, dasar in TAMBAHAN:
    hits = PP.with_context(active_test=False).search([("name", "=", nama)], limit=1)
    if not hits:
        say("     %-32s (tidak ditemukan)" % nama)
        continue
    kini = float(hits[0].standard_price or 0)
    tanda = "SUDAH DIPERBAIKI" if abs(kini - baru) < 0.005 else "MASIH %s" % money(kini)
    say("     %-32s seharusnya %-14s %s   (%s)" % (nama[:32], ("%.4f" % baru), tanda, dasar[:44]))

say("")
say("   integritas: produk POS %d | item pricelist %d | baris BOM %d" % (
    PP.search_count([("available_in_pos", "=", True), ("sale_ok", "=", True)]),
    env["product.pricelist.item"].search_count([]),
    env["mrp.bom.line"].search_count([])))
say("=" * 116)
