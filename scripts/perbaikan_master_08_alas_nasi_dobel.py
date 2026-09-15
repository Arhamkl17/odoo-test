# -*- coding: utf-8 -*-
"""
perbaikan_master_08_alas_nasi_dobel.py — rapikan baris `ALAS NASI BUNDAR` dobel (13 Sep 2026).

MASALAH
  5 menu berisi **dua baris** `ALAS NASI BUNDAR 1 LEMBAR` padahal menunya **1 porsi**
  (BERAS 74,20 GRM = 1 porsi nasi, AYAM CUT 9 = 1 potong):
      BIG HEMAT 1 · BIG HEMAT 2 · BIG HEMAT 3 · PKG SAMBAL ORI SAYAP ·
      PKG SAMBAL ORI DADA/PAHA ATAS
  Akibatnya HPP masing-masing kelebihan Rp 106,67/porsi (harga alas nasi sekarang).

  Baris dobel itu **tertulis di berkas klien sendiri** (`mrp_bom Barang Combo.xlsx`, sheet
  `FIX BOM GANTI COMBO` — dua baris `ALAS NASI BUNDAR 1 LEMBAR` terpisah dalam satu blok),
  jadi ini bukan bug impor. Pola yang sama sudah pernah ditangani: `TEPUNG MIX GEYUKSSS`
  dobel di TAHU/TEMPE CRISPY (lihat `perbaikan_master_04_takaran_resep.py`).

BUKTI BAHWA 2 LEMBAR ITU KELIRU (bukan takaran dapur)
  1. **Kembaran komposisi**: `PKG SAMBAL ORI PAHA BAWAH` isinya sama dengan
     `PKG SAMBAL ORI SAYAP`/`DADA/PAHA ATAS` (nasi + ayam cut 9 + tepung + minyak padat +
     es kristal + sambal korek + minyak + es teh) tetapi **hanya 1 lembar**. Begitu juga
     `BIG HEMAT 4` (1 porsi, 1 lembar). Yang dobel justru outlier.
  2. **Uji pemakaian 3 bulan klien sendiri** (`PERMINTAAN_DATA_BIAYA_KLIEN.md`):
        ALAS NASI BUNDAR          30.162 LEMBAR
        porsi nasi (beras/garam)  20.070
        porsi ayam (AYAM CUT 9 + CUT 2) 28.105
     Aturan "1 lembar per **porsi nasi**" → prediksi 20.070 (meleset −10.092, salah).
     Aturan "1 lembar per **porsi yang disajikan**" → 28.105 porsi ayam + nasi lepas
     ≈ 31.005 vs 30.162 pemakaian nyata (**cocok 2,8%**). Jadi pemakaian alas nasi
     mengikuti porsi disajikan, dan 1 porsi = 1 lembar — bukan 2.

YANG **TIDAK** DIUBAH
  `PAKET MEVVAH BERDUA` juga punya 2 baris alas nasi, tapi memang **2 porsi** (AYAM CUT 9 ×2,
  ES KRISTAL ×2, GELAS ×2) → 2 lembar = benar.
  Menu **2 porsi** yang hanya 1 lembar (`PAKET YUKSSS MABAR`, `PKG LOKAL DUO`, keduanya
  BERAS 148,4 = 2 porsi) justru **kebalikannya** (kurang) — itu di luar lingkup skrip ini,
  perlu keputusan pemilik karena menaikkan biaya.

DAMPAK
  HPP 5 menu turun Rp 106,67 → margin naik ±0,5%. `standard_price` menu tersebut
  **ikut diselaraskan** ke HPP baru supaya tidak kembali ada dua angka biaya (§8.8).
  Baris BOM 942 → 937.

  default : dry-run penuh.
  RUN=1   : eksekusi.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_08_alas_nasi_dobel.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_08_alas_nasi_dobel.py
"""
import os

RUN = os.environ.get("RUN") == "1"
PL_NORMAL = 3

TARGET = {                      # menu 1 porsi yang alas nasinya dobel
    "BIG HEMAT 1",
    "BIG HEMAT 2",
    "BIG HEMAT 3",
    "PKG SAMBAL ORI SAYAP",
    "PKG SAMBAL ORI DADA/PAHA ATAS",
}
BAHAN_ALAS = "ALAS NASI BUNDAR"

cr = env.cr
say = lambda m="": print(m)
money = lambda x: "{:>11,.2f}".format(float(x or 0))


def hpp_of(tid):
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tid,))
    return float(cr.fetchone()[0] or 0)


def standard_price(pp_id):
    cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (pp_id,))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else None


def harga_jual(tid):
    cr.execute("SELECT fixed_price FROM product_pricelist_item "
               "WHERE pricelist_id=%s AND product_tmpl_id=%s LIMIT 1", (PL_NORMAL, tid))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


# ------------------------------------------------------------------ DIAGNOSA
cr.execute("""
    SELECT b.product_tmpl_id,
           pt.name->>'en_US',
           COUNT(*) FILTER (WHERE ing.name->>'en_US' = %s)                        AS n_alas,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = %s), 0) AS q_alas,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = 'BERAS'), 0) AS q_beras,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' LIKE 'AYAM CUT%%'), 0) AS q_ayam
      FROM mrp_bom b
      JOIN mrp_bom_line bl ON bl.bom_id = b.id
      JOIN product_product cp ON cp.id = bl.product_id
      JOIN product_template ing ON ing.id = cp.product_tmpl_id
      JOIN product_template pt ON pt.id = b.product_tmpl_id
     WHERE b.active
     GROUP BY 1, 2
    HAVING COUNT(*) FILTER (WHERE ing.name->>'en_US' = %s) >= 1
     ORDER BY 3 DESC, 2
""", (BAHAN_ALAS, BAHAN_ALAS, BAHAN_ALAS))

diagnosa = cr.fetchall()
say("=" * 116)
say("RAPIKAN BARIS ALAS NASI BUNDAR DOBEL   |   RUN=%s   |   %s" % (RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 116)
say("")
say("[DIAGNOSA] menu yang memakai %s" % BAHAN_ALAS)
say("   %-46s %6s %7s %8s %7s   %s" % ("menu", "baris", "lembar", "beras", "porsi", "catatan"))
say("   " + "-" * 108)
for tid, nama, n_alas, q_alas, q_beras, q_ayam in diagnosa:
    porsi = max(q_beras / 74.2, q_ayam)
    if n_alas > 1 and porsi <= 1.01:
        cat = "DOBEL untuk 1 porsi -> dirapikan"
    elif n_alas > 1:
        cat = "%d lembar utk %g porsi -> benar (tidak diubah)" % (q_alas, porsi)
    elif q_alas < porsi - 0.01:
        cat = "kurang: %g lembar utk %g porsi (di luar lingkup)" % (q_alas, porsi)
    else:
        cat = "ok"
    say("   %-46s %6d %7g %8g %7g   %s" % (nama[:46], n_alas, q_alas, q_beras, porsi, cat))

# ------------------------------------------------------------------ GUARD
say("")
say("[GUARD]")
rencana, lewat = [], []
for tid, nama, n_alas, q_alas, q_beras, q_ayam in diagnosa:
    if nama not in TARGET:
        continue
    cr.execute("""
        SELECT bl.id, bl.product_qty FROM mrp_bom_line bl
          JOIN mrp_bom b ON b.id = bl.bom_id
          JOIN product_product cp ON cp.id = bl.product_id
          JOIN product_template ing ON ing.id = cp.product_tmpl_id
         WHERE b.product_tmpl_id = %s AND b.active AND ing.name->>'en_US' = %s
         ORDER BY bl.id
    """, (tid, BAHAN_ALAS))
    baris = cr.fetchall()
    if len(baris) == 1:
        lewat.append("%s: sudah 1 baris — dilewati (idempotent)" % nama)
        continue
    if len(baris) != 2 or any(abs(float(q) - 1.0) > 1e-9 for _, q in baris):
        lewat.append("%s: %d baris qty %s — TIDAK sesuai pola, dilewati"
                     % (nama, len(baris), [q for _, q in baris]))
        continue
    if q_beras > 74.2 + 0.01 or q_ayam > 1.01:
        lewat.append("%s: bukan menu 1 porsi (beras %g, ayam %g) — dilewati"
                     % (nama, q_beras, q_ayam))
        continue
    cr.execute("SELECT id, product_tmpl_id FROM product_product WHERE product_tmpl_id=%s", (tid,))
    pp_id = cr.fetchone()[0]
    cr.execute("""SELECT b.id FROM mrp_bom b WHERE b.product_tmpl_id=%s AND b.active""", (tid,))
    bom_id = cr.fetchone()[0]
    rencana.append(dict(tid=tid, nama=nama, bom_id=bom_id, pp_id=pp_id,
                        buang=baris[1], simpan=baris[0],
                        hpp0=hpp_of(tid), sp0=standard_price(pp_id), jual=harga_jual(tid)))

say("   menu sesuai pola dobel-1porsi : %d dari %d target" % (len(rencana), len(TARGET)))
for x in lewat:
    say("   !! %s" % x)
if not rencana:
    say("")
    say("   Tidak ada yang perlu dikerjakan — berhenti.")
    say("=" * 116)
    cr.rollback()
    raise SystemExit(0)

say("")
say("   %-46s %6s  %13s %13s %11s %8s %8s" % (
    "menu", "buang", "HPP lama", "HPP baru", "jual", "margin", "m.baru"))
say("   " + "-" * 112)
for r in rencana:
    h1 = r["hpp0"] - 106.6666666667
    r["hpp1"] = h1
    r["sp1"] = round(h1, 2)
    m0 = (1 - r["hpp0"] / r["jual"]) * 100 if r["jual"] else 0
    m1 = (1 - h1 / r["jual"]) * 100 if r["jual"] else 0
    say("   %-46s line#%s %s %s %11s %7.1f%% %7.1f%%" % (
        r["nama"][:46], r["buang"][0], money(r["hpp0"]), money(h1), money(r["jual"]), m0, m1))

cr.execute("SELECT count(*) FROM mrp_bom_line")
baris0 = cr.fetchone()[0]
say("")
say("   standard_price sebelum : %s" % ", ".join(
    "%s=%s" % (r["nama"], "kosong" if r["sp0"] is None else "%.2f" % r["sp0"]) for r in rencana))
say("   baris BOM sebelum      : %d" % baris0)

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 116)
    cr.rollback()
    raise SystemExit(0)

# ------------------------------------------------------------------ EKSEKUSI
say("")
say("[EKSEKUSI]")
BLine = env["mrp.bom.line"]
PP = env["product.product"]
for r in rencana:
    BLine.browse(r["buang"][0]).unlink()
    say("   %-46s hapus line id %s (sisakan id %s)" % (r["nama"][:46], r["buang"][0], r["simpan"][0]))
cr.flush()
for r in rencana:
    PP.browse(r["pp_id"]).with_context(disable_auto_revaluation=True).standard_price = r["sp1"]
cr.flush()
cr.commit()
say("   [COMMITTED] %d menu" % len(rencana))

# ------------------------------------------------------------------ VERIFIKASI
say("")
say("=" * 116)
say("[VERIFIKASI]")
salah = 0
for r in rencana:
    cr.execute("""
        SELECT count(*) FROM mrp_bom_line bl JOIN mrp_bom b ON b.id = bl.bom_id
          JOIN product_product cp ON cp.id = bl.product_id
          JOIN product_template ing ON ing.id = cp.product_tmpl_id
         WHERE b.product_tmpl_id = %s AND b.active AND ing.name->>'en_US' = %s
    """, (r["tid"], BAHAN_ALAS))
    n = cr.fetchone()[0]
    h = hpp_of(r["tid"])
    sp = standard_price(r["pp_id"])
    ok = (n == 1 and abs(h - r["hpp1"]) < 0.02 and sp is not None and abs(sp - r["hpp1"]) < 0.02)
    if not ok:
        salah += 1
    say("   %-46s baris=%d  HPP=%s  standard_price=%s   %s" % (
        r["nama"][:46], n, money(h), "kosong" if sp is None else money(sp),
        "OK" if ok else "!! TIDAK SESUAI"))
say("   menu sesuai target : %d / %d" % (len(rencana) - salah, len(rencana)))

cr.execute("SELECT count(*) FROM mrp_bom_line")
baris1 = cr.fetchone()[0]
say("")
say("   baris BOM : %d → %d  (berkurang %d)" % (baris0, baris1, baris0 - baris1))

# pastikan seluruh menu tetap punya satu angka biaya (§8.8)
cr.execute("""
    WITH h AS (
      SELECT b.product_tmpl_id tid,
             SUM(l.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)) h
        FROM mrp_bom b JOIN mrp_bom_line l ON l.bom_id = b.id
        JOIN product_product cp ON cp.id = l.product_id
       WHERE b.active GROUP BY 1)
    SELECT count(*) FILTER (WHERE (pp.standard_price->>'1') IS NULL),
           count(*) FILTER (WHERE abs(h.h - (pp.standard_price->>'1')::numeric) > 0.01),
           count(*)
      FROM h JOIN product_product pp ON pp.product_tmpl_id = h.tid
""")
n_kosong, n_beda, n_total = cr.fetchone()
say("   menu dua angka biaya: %d dari %d  (sp kosong %d)" % (n_beda, n_total, n_kosong))

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
say("   integritas: produk POS %d | item pricelist %d | BOM aktif %d" % (
    PP.search_count([("available_in_pos", "=", True), ("sale_ok", "=", True)]),
    env["product.pricelist.item"].search_count([]),
    env["mrp.bom"].search_count([("active", "=", True)])))
say("=" * 116)
