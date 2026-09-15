# -*- coding: utf-8 -*-
"""
perbaikan_master_03_harga_bahan_tanpa_sumber.py — ISI HARGA 8 BAHAN (13 Sep 2026).

LATAR BELAKANG
  Hasil audit `AUDIT_MASTER_DATA_2026-09-13.md` §4.4: 12 dari 52 komponen BOM tidak
  ada di berkas harga klien `HARGA BAHAN BAKU GUDANG.xlsx` (sheet Agustus). Skrip ini
  memberi harga yang bisa dipertanggungjawabkan untuk 8 di antaranya.

  Sumber yang dipakai (berurut prioritas):
    1. BERKAS KLIEN   — `HARGA BAHAN BAKU GUDANG.xlsx` (harga beli terkini, Agustus)
                        dan kolom **Modal** di `Produk (product.template) (87).xlsx`
                        (snapshot harga beli versi klien).
    2. RISET PASAR    — panel harga pangan pemda + harga grosir online (Sep 2026),
                        untuk bahan yang tidak ada di berkas klien sama sekali.

TABEL PERUBAHAN
  | bahan                | tmpl | UoM   | dari    | menjadi | dasar                                    |
  |----------------------|------|-------|--------:|--------:|------------------------------------------|
  | BUBUK KEJU           |  462 | GRM   |     150 |      85 | kolom Modal klien (Rp85.000/kg)          |
  | BUBUK BLACKCURRENT   |  481 | GRM   |     120 |      92 | kolom Modal klien (Rp92.000/kg)          |
  | ES KRISTAL           |  644 | GRM   |       5 |     2,5 | riset: es kristal Rp1.000–2.500/kg       |
  | NUGGET AYAM          |  649 | PCS   |   1.500 |     900 | riset: nugget 1 kg Rp34.000–48.000, ~50 pcs/kg |
  | MIKA BUNDAR          |  494 | PCS   |     500 |     390 | berkas klien "Mika Burger" Rp390/pcs     |
  | TAHU                 |  646 | GRM   |      30 |      12 | riset: tahu putih Rp10.000–11.071/kg     |
  | TEMPE                |  645 | GRM   |      40 |      15 | riset: tempe Rp12.000–13.943/kg          |
  | TELUR                |  475 | BUTIR |   2.000 |   1.800 | riset: Makassar Rp24.000/kg ≈ Rp1.500/butir, rak Rp53.000/30 = Rp1.767 |

  SENGAJA TIDAK DIUBAH (sudah punya dasar harga):
    SAMBAL TOMAT MALINO 95,19  → di antara harga sambal klien (Ijo 80; Rica/Korek 102,79)
    AIR GALON 1,19             → supplierinfo 1,18
    NASI 1.172,69 & ES TEH 1.085,11 → produk menu, biayanya turunan resep sendiri

AMAN DARI JURNAL
  Kategori bahan ini semuanya `cost_method = fifo`. Sesuai
  `stock_account/models/product.py::_change_standard_price`, produk FIFO DILEWATI sehingga
  menulis `standard_price` TIDAK membuat revaluasi/jurnal. Order & stok historis tidak disentuh.

  CATATAN: HPP menu di laporan dihitung ulang dari `standard_price`, jadi margin langsung
  berubah tanpa JE. Bila perlu koreksi HPP yang sudah diposting, pakai pola JE penyesuaian
  per bulan di `CARA_IMPOR_HARGA_BELI.md` §3 — BUKAN skrip ini.

  Idempotent. Dry-run penuh (`env.cr.rollback()`).

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_03_harga_bahan_tanpa_sumber.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/perbaikan_master_03_harga_bahan_tanpa_sumber.py
"""
import os

RUN = os.environ.get("RUN") == "1"

PL_NORMAL = 3
TARGET_MARGIN = 45.0

# (nama bahan, harga baru, UoM, harga lama yang diharapkan, alasan)
TARGET = [
    ("BUBUK KEJU",         85.0,  "GRM",   150.0,               "kolom Modal klien (Rp85.000/kg)"),
    ("BUBUK BLACKCURRENT", 92.0,  "GRM",   120.0,               "kolom Modal klien (Rp92.000/kg)"),
    ("ES KRISTAL",         2.5,   "GRM",   5.0,                 "riset: es kristal Rp1.000-2.500/kg"),
    ("NUGGET AYAM",        900.0, "PCS",   1500.0,              "riset: nugget 1 kg Rp34rb-48rb, ~50 pcs/kg"),
    ("MIKA BUNDAR",        390.0, "PCS",   500.0,               "berkas klien 'Mika Burger' Rp390/pcs"),
    ("TAHU",               12.0,  "GRM",   30.0,                "riset: tahu putih Rp10.000-11.071/kg"),
    ("TEMPE",              15.0,  "GRM",   40.0,                "riset: tempe Rp12.000-13.943/kg"),
    ("TELUR",              1800.0, "BUTIR", 2000.0,             "riset: Makassar ~Rp1.500-1.767/butir"),
]

cr = env.cr
PP = env["product.product"]
PT = env["product.template"]

say = lambda m="": print(m)
money = lambda x: "{:>14,.2f}".format(float(x or 0))


def hpp_of(tmpl_id):
    """HPP dari resep aktif: Σ(qty x standard_price). 0 kalau tanpa resep."""
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


def harga_jual(tmpl_id):
    cr.execute("""SELECT fixed_price FROM product_pricelist_item
                   WHERE pricelist_id=%s AND product_tmpl_id=%s LIMIT 1""",
               (PL_NORMAL, tmpl_id))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


def qty_dipakai(pp_id, tmpl_id):
    cr.execute("""SELECT COALESCE(SUM(bl.product_qty), 0)
                    FROM mrp_bom_line bl JOIN mrp_bom b ON b.id = bl.bom_id
                   WHERE bl.product_id = %s AND b.product_tmpl_id = %s AND b.active""",
               (pp_id, tmpl_id))
    return float(cr.fetchone()[0] or 0)


# ================================================================ GUARD
say("=" * 118)
say("ISI HARGA 8 BAHAN TANPA SUMBER KLIEN   |   RUN=%s   |   %s" % (RUN, "TULIS" if RUN else "DRY-RUN"))
say("=" * 118)
say("")

rencana, masalah = [], []
for nama, baru, uom, lama_harap, alasan in TARGET:
    hits = PP.with_context(active_test=False).search([("name", "=", nama)])
    if len(hits) != 1:
        masalah.append("%s: ditemukan %d produk (harus 1)" % (nama, len(hits)))
        continue
    p = hits[0]
    t = p.product_tmpl_id
    uom_aktual = t.uom_id.name or ""
    lama_aktual = float(p.standard_price or 0)
    if abs(lama_aktual - lama_harap) > 0.01:
        masalah.append("%s: harga sekarang %s, diharapkan %s — DILEWATI (DB berubah?)"
                       % (nama, money(lama_aktual), money(lama_harap)))
        continue
    if uom_aktual != uom:
        masalah.append("%s: UoM sekarang %r, diharapkan %r — DILEWATI" % (nama, uom_aktual, uom))
        continue
    # jumlah resep yang memakai
    cr.execute("""SELECT COUNT(DISTINCT b.product_tmpl_id) FROM mrp_bom_line bl
                   JOIN mrp_bom b ON b.id=bl.bom_id WHERE bl.product_id=%s AND b.active""", (p.id,))
    nmenu = cr.fetchone()[0]
    rencana.append(dict(nama=nama, pp=p, tmpl=t, uom=uom, lama=lama_aktual, baru=baru,
                        alasan=alasan, nmenu=nmenu))

say("[GUARD]")
say("   bahan siap diubah : %d dari %d" % (len(rencana), len(TARGET)))
for m in masalah:
    say("   !! %s" % m)
if not rencana:
    say("")
    say("   Tidak ada yang bisa dikerjakan — berhenti.")
    say("=" * 118)
    cr.rollback()
    raise SystemExit(0)

say("")
say("   %-4s %-22s %-6s %14s %14s %-7s %-38s" % (
    "tmpl", "bahan", "UoM", "harga lama", "harga baru", "menu", "dasar"))
say("   " + "-" * 112)
for r in rencana:
    say("   %-4s %-22s %-6s %s %s %-7s %-38s" % (
        r["tmpl"].id, r["nama"][:22], r["uom"], money(r["lama"]), money(r["baru"]),
        r["nmenu"], r["alasan"][:38]))

# ================================================================ DAMPAK HPP MENU
terdampak = {}
for r in rencana:
    cr.execute("""SELECT DISTINCT b.product_tmpl_id FROM mrp_bom_line bl
                   JOIN mrp_bom b ON b.id=bl.bom_id
                  WHERE bl.product_id=%s AND b.active""", (r["pp"].id,))
    for (tid,) in cr.fetchall():
        terdampak.setdefault(tid, [])
        delta = qty_dipakai(r["pp"].id, tid) * (r["baru"] - r["lama"])
        if delta:
            terdampak[tid].append((r["nama"], delta))

say("")
say("[DAMPAK HPP MENU] %d resep memakai bahan yang diubah" % len(terdampak))
hasil = []
for tid, deltas in terdampak.items():
    t = PT.browse(tid)
    h0 = hpp_of(tid)
    harga = harga_jual(tid)
    h1 = h0 + sum(d for _n, d in deltas)
    hasil.append((t, h0, h1, harga, deltas))
hasil.sort(key=lambda x: (1 - x[2] / x[3]) * 100 if x[3] else 999)

n_hpp_turun = len([1 for _t, h0, h1, _h, _d in hasil if h1 < h0])
n_hpp_naik = len([1 for _t, h0, h1, _h, _d in hasil if h1 > h0])
say("   HPP turun: %d  |  HPP naik: %d" % (n_hpp_turun, n_hpp_naik))
say("")
say("   %-44s %13s %13s %10s %8s %8s" % (
    "menu", "HPP lama", "HPP baru", "jual", "margin", "m.baru"))
say("   " + "-" * 104)
for t, h0, h1, harga, _d in hasil[:22]:
    m0 = (1 - h0 / harga) * 100 if harga else 0
    m1 = (1 - h1 / harga) * 100 if harga else 0
    say("   %-44s %s %s %13s %7.1f%% %7.1f%%" % (
        t.display_name[:44], money(h0), money(h1), money(harga), m0, m1))

bawah = [x for x in hasil if x[3] and (1 - x[2] / x[3]) * 100 < TARGET_MARGIN]
say("")
say("   margin < %.0f%% SESUDAH perbaikan: %d menu" % (TARGET_MARGIN, len(bawah)))
for t, h0, h1, harga, _d in bawah[:15]:
    say("     %-44s %13s  margin %5.1f%%" % (t.display_name[:44], money(h1),
                                             (1 - h1 / harga) * 100))

# contoh rincian satu menu
say("")
say("   contoh rincian (BLACKCURRANT):")
for t, h0, h1, harga, deltas in hasil:
    if t.id == PT.search([("name", "=", "BLACKCURRANT")], limit=1).id:
        for n, d in deltas:
            say("     %-24s %+10.2f" % (n, d))
        say("     %-24s %13s → %s   margin %.1f%% → %.1f%%" % (
            "TOTAL HPP", money(h0), money(h1),
            (1 - h0 / harga) * 100 if harga else 0, (1 - h1 / harga) * 100 if harga else 0))

# ================================================================ DRY-RUN
if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan ditulis. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 118)
    cr.rollback()
    raise SystemExit(0)

# ================================================================ EKSEKUSI
say("")
say("[EKSEKUSI] menulis standard_price (produk FIFO → tanpa revaluasi/jurnal)")
for r in rencana:
    r["pp"].with_context(disable_auto_revaluation=True).standard_price = r["baru"]
    say("   %-22s %s → %s  (%s)" % (r["nama"][:22], money(r["lama"]), money(r["baru"]), r["uom"]))
cr.flush()
cr.commit()
say("   [COMMITTED] %d bahan" % len(rencana))

# ================================================================ VERIFIKASI
say("")
say("=" * 118)
say("[VERIFIKASI]")
salah = 0
for r in rencana:
    cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s",
               (r["pp"].id,))
    kini = float(cr.fetchone()[0] or 0)
    if abs(kini - r["baru"]) > 0.005:
        salah += 1
        say("   !! %s masih %s (seharusnya %s)" % (r["nama"], money(kini), money(r["baru"])))
say("   bahan sesuai target : %d / %d" % (len(rencana) - salah, len(rencana)))

say("")
say("   HPP menu terdampak (sebelum → sesudah):")
for r in rencana:
    pass
for tid, deltas in sorted(terdampak.items()):
    t = PT.browse(tid)
    say("     %-44s %13s → %13s  (%+.2f)" % (
        t.display_name[:44], money(hpp_of(tid) - sum(d for _n, d in deltas)),
        money(hpp_of(tid)), sum(d for _n, d in deltas)))

say("")
say("   bahan yang SENGAJA tidak diubah:")
for nm in ("SAMBAL TOMAT MALINO", "AIR GALON", "NASI", "ES TEH"):
    hits = PP.with_context(active_test=False).search([("name", "=", nm)], limit=1)
    if hits:
        say("     %-22s %s" % (nm, money(float(hits[0].standard_price or 0))))

say("")
say("   supplierinfo yang kini BERBEDA dari standard_price (perlu dibenahi terpisah):")
for r in rencana:
    cr.execute("""SELECT rp.name, si.price FROM product_supplierinfo si
                   JOIN res_partner rp ON rp.id=si.partner_id
                  WHERE si.product_tmpl_id=%s ORDER BY si.price""", (r["tmpl"].id,))
    for sp_name, price in cr.fetchall():
        if abs(float(price) - r["baru"]) > 0.005:
            say("     %-22s sistem=%s  supplier %-24s %s" % (
                r["nama"][:22], money(r["baru"]), sp_name[:24], money(price)))

say("")
say("   POS historis tidak disentuh (bukti):")
cr.execute("SELECT to_char(date_order,'YYYY-MM'), count(*), COALESCE(SUM(amount_total),0) "
           "FROM pos_order GROUP BY 1 ORDER BY 1")
for m, n, tot in cr.fetchall():
    say("     %s : %d order / %s" % (m, n, money(tot)))
say("=" * 118)
