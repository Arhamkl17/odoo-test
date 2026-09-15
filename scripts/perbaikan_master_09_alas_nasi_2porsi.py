# -*- coding: utf-8 -*-
"""
perbaikan_master_09_alas_nasi_2porsi.py — lengkapi `ALAS NASI BUNDAR` menu 2 porsi (13 Sep 2026).

MASALAH
  3 menu berisi **2 porsi** (BERAS 148,40 GRM = 2 × 74,20, AYAM CUT 9 = 2 potong) tetapi
  hanya **1 lembar** `ALAS NASI BUNDAR` — arah sebaliknya dari temuan §8.10:

      PAKET YUKSSS MABAR   AYAM CUT 9 1+1 = 2 PTG, BERAS 148,40 GRM, ALAS NASI 1 LEMBAR
      PKG LOKAL DUO        AYAM CUT 9 1+1 = 2 PTG, BERAS 74,20×2 = 148,40 GRM, ALAS NASI 1
      PAKET GEPREK BAKAR   AYAM CUT 9 = 2 PTG,   BERAS 148,40 GRM, ALAS NASI 1 LEMBAR

DASAR (aturan yang sudah diuji di §8.10)
  Aturan nyata klien = **1 lembar alas nasi per porsi yang disajikan**, dibuktikan dengan
  pemakaian 3 bulan klien sendiri: 30.162 LEMBAR pemakaian vs 28.105 porsi ayam + nasi lepas
  (±31.005, cocok 2,8%). Aturan "1 lembar per porsi nasi" sudah terbukti salah (meleset
  −10.092). Karena itu menu 2 porsi seharusnya 2 lembar.

  Bandingkan yang sudah benar di sistem: `PAKET MEVVAH BERDUA` (2 porsi) = 2 lembar, dan
  `PAKET BIG ORDER CRISPY MIX` (4 porsi) = 4 lembar.

DAMPAK
  HPP ketiga menu **naik** Rp 106,67/porsi (harga alas nasi) → margin turun ±0,2–0,5%
  (arah sebaliknya dari koreksi §8.1–§8.10, dan memang begitu seharusnya: ini melengkapi
  biaya yang belum tercatat). `standard_price` ketiga menu ikut diselaraskan ke HPP baru
  supaya tetap satu angka biaya (§8.8). Baris BOM 937 → 940.

  default : dry-run penuh.
  RUN=1   : eksekusi.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_09_alas_nasi_2porsi.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_09_alas_nasi_2porsi.py
"""
import os

RUN = os.environ.get("RUN") == "1"
PL_NORMAL = 3

BAHAN_ALAS = "ALAS NASI BUNDAR"
TARGET = {                          # menu 2 porsi yang alas nasinya kurang 1 lembar
    "PAKET YUKSSS MABAR",
    "PKG LOKAL DUO",
    "PAKET GEPREK BAKAR",
}
BERAS_PER_PORSI = 74.2

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


# ------------------------------------------------------------------ REFERENSI ALAS NASI
cr.execute("""
    SELECT pp.id, pt.id, pt.uom_id, COALESCE((pp.standard_price->>'1')::numeric, 0)
      FROM product_product pp JOIN product_template pt ON pt.id = pp.product_tmpl_id
     WHERE pt.name->>'en_US' = %s
""", (BAHAN_ALAS,))
ref = cr.fetchall()
say("=" * 114)
say("LENGKAPI ALAS NASI BUNDAR MENU 2 PORSI   |   RUN=%s   |   %s" % (RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 114)
say("")
say("[GUARD]")
if len(ref) != 1:
    say("   !! produk %r ditemukan %d — berhenti demi keamanan." % (BAHAN_ALAS, len(ref)))
    cr.rollback()
    raise SystemExit(1)
pp_alas, tmpl_alas, uom_alas, harga_alas = ref[0]
harga_alas = float(harga_alas)
say("   produk acuan  : %s → product_product %d | uom_id %d | harga %s" % (
    BAHAN_ALAS, pp_alas, uom_alas, money(harga_alas)))

# ------------------------------------------------------------------ DIAGNOSA + RENCANA
say("")
rencana, lewat = [], []
cr.execute("""
    SELECT b.product_tmpl_id, pt.name->>'en_US',
           COUNT(*) FILTER (WHERE ing.name->>'en_US' = %s)                        AS n_alas,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = %s), 0) AS q_alas,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = 'BERAS'), 0) AS q_beras,
           COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' LIKE 'AYAM CUT%%'), 0) AS q_ayam
      FROM mrp_bom b
      JOIN mrp_bom_line bl ON bl.bom_id = b.id
      JOIN product_product cp ON cp.id = bl.product_id
      JOIN product_template ing ON ing.id = cp.product_tmpl_id
      JOIN product_template pt ON pt.id = b.product_tmpl_id
     WHERE b.active AND pt.name->>'en_US' = ANY(%s)
     GROUP BY 1, 2
""", (BAHAN_ALAS, BAHAN_ALAS, list(TARGET)))
for tid, nama, n_alas, q_alas, q_beras, q_ayam in cr.fetchall():
    porsi = max(q_beras / BERAS_PER_PORSI, q_ayam)
    if n_alas >= 2:
        lewat.append("%s: sudah %d baris alas nasi — dilewati (idempotent)" % (nama, n_alas))
        continue
    if n_alas != 1 or abs(float(q_alas) - 1.0) > 1e-9:
        lewat.append("%s: pola alas nasi bukan 1 baris × 1 lembar (baris %d, %g lembar) — dilewati"
                     % (nama, n_alas, q_alas))
        continue
    if abs(porsi - 2.0) > 0.01:
        lewat.append("%s: bukan menu 2 porsi (beras %g, ayam %g → %g porsi) — dilewati"
                     % (nama, q_beras, q_ayam, porsi))
        continue
    cr.execute("SELECT id FROM product_product WHERE product_tmpl_id=%s", (tid,))
    pp_id = cr.fetchone()[0]
    cr.execute("SELECT id FROM mrp_bom WHERE product_tmpl_id=%s AND active", (tid,))
    bom_id = cr.fetchone()[0]
    rencana.append(dict(tid=tid, nama=nama, bom_id=bom_id, pp_id=pp_id, porsi=porsi,
                        hpp0=hpp_of(tid), sp0=standard_price(pp_id), jual=harga_jual(tid)))

if not rencana:
    say("   Tidak ada yang perlu dikerjakan.")
    for x in lewat:
        say("   !! %s" % x)
    say("=" * 114)
    cr.rollback()
    raise SystemExit(0)

say("   menu siap dilengkapi : %d dari %d target" % (len(rencana), len(TARGET)))
for x in lewat:
    say("   !! %s" % x)
say("")
say("   %-26s %6s %13s %13s %11s %8s %8s" % (
    "menu", "porsi", "HPP lama", "HPP baru", "jual", "margin", "m.baru"))
say("   " + "-" * 108)
for r in rencana:
    r["hpp1"] = r["hpp0"] + harga_alas
    r["sp1"] = round(r["hpp1"], 2)
    m0 = (1 - r["hpp0"] / r["jual"]) * 100 if r["jual"] else 0
    m1 = (1 - r["hpp1"] / r["jual"]) * 100 if r["jual"] else 0
    say("   %-26s %6g %s %s %11s %7.1f%% %7.1f%%" % (
        r["nama"][:26], r["porsi"], money(r["hpp0"]), money(r["hpp1"]), money(r["jual"]), m0, m1))

cr.execute("SELECT count(*) FROM mrp_bom_line")
baris0 = cr.fetchone()[0]
say("")
say("   rencana: +1 baris %s × 1 LEMBAR per menu (%d baris baru)" % (BAHAN_ALAS, len(rencana)))
say("   baris BOM sebelum: %d  →  sesudah: %d" % (baris0, baris0 + len(rencana)))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 114)
    cr.rollback()
    raise SystemExit(0)

# ------------------------------------------------------------------ EKSEKUSI
say("")
say("[EKSEKUSI]")
BLine = env["mrp.bom.line"]
PP = env["product.product"]
new_ids = []
for r in rencana:
    line = BLine.create({
        "bom_id": r["bom_id"],
        "product_id": pp_alas,
        "product_qty": 1.0,
        "product_uom_id": uom_alas,
    })
    new_ids.append(line.id)
    say("   %-26s + baris baru id %s  (%s × 1 LEMBAR)" % (r["nama"][:26], line.id, BAHAN_ALAS))
cr.flush()
for r in rencana:
    PP.browse(r["pp_id"]).with_context(disable_auto_revaluation=True).standard_price = r["sp1"]
cr.flush()
cr.commit()
say("   [COMMITTED] %d menu" % len(rencana))

# ------------------------------------------------------------------ VERIFIKASI
say("")
say("=" * 114)
say("[VERIFIKASI]")
salah = 0
for r in rencana:
    cr.execute("""
        SELECT COUNT(*), COALESCE(SUM(bl.product_qty), 0), COALESCE(MAX(u.name->>'en_US'), '-')
          FROM mrp_bom_line bl
          JOIN mrp_bom b ON b.id = bl.bom_id
          JOIN product_product cp ON cp.id = bl.product_id
          JOIN product_template ing ON ing.id = cp.product_tmpl_id
          JOIN uom_uom u ON u.id = bl.product_uom_id
         WHERE b.product_tmpl_id = %s AND b.active AND ing.name->>'en_US' = %s
    """, (r["tid"], BAHAN_ALAS))
    n, q, uom = cr.fetchone()
    h = hpp_of(r["tid"])
    sp = standard_price(r["pp_id"])
    ok = (n == 2 and abs(float(q) - 2.0) < 1e-9 and uom == "LEMBAR"
          and abs(h - r["hpp1"]) < 0.02 and sp is not None and abs(sp - r["hpp1"]) < 0.02)
    if not ok:
        salah += 1
    say("   %-26s baris=%d lembar=%g uom=%s  HPP=%s  sp=%s   %s" % (
        r["nama"][:26], n, q, uom, money(h), "kosong" if sp is None else money(sp),
        "OK" if ok else "!! TIDAK SESUAI"))
say("   menu sesuai target : %d / %d" % (len(rencana) - salah, len(rencana)))

cr.execute("SELECT count(*) FROM mrp_bom_line")
baris1 = cr.fetchone()[0]
say("")
say("   baris BOM : %d → %d  (bertambah %d)" % (baris0, baris1, baris1 - baris0))

# konsistensi aturan "1 lembar per porsi" untuk SEMUA menu berbahan alas nasi
cr.execute("""
    WITH x AS (
      SELECT b.product_tmpl_id tid, pt.name->>'en_US' nama,
             COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = %s), 0) AS q_alas,
             COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = 'BERAS'), 0) AS q_beras,
             COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' LIKE 'AYAM CUT%%'), 0) AS q_ayam
        FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
        JOIN product_product cp ON cp.id = bl.product_id
        JOIN product_template ing ON ing.id = cp.product_tmpl_id
        JOIN product_template pt ON pt.id = b.product_tmpl_id
       WHERE b.active GROUP BY 1, 2
      HAVING COALESCE(SUM(bl.product_qty) FILTER (WHERE ing.name->>'en_US' = %s), 0) > 0)
    SELECT count(*) FILTER (WHERE q_alas < GREATEST(q_beras/74.2, q_ayam) - 0.01) AS kurang,
           count(*) FILTER (WHERE q_alas > GREATEST(q_beras/74.2, q_ayam) + 0.01) AS lebih,
           count(*) AS total
      FROM x
""", (BAHAN_ALAS, BAHAN_ALAS))
kurang, lebih, total = cr.fetchone()
say("   konsistensi \"1 lembar per porsi\" pada %d menu beralas nasi: kurang %d, lebih %d" % (
    total, kurang, lebih))

# satu angka biaya tetap terjaga
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
say("=" * 114)
