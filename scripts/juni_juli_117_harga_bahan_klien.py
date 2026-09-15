# -*- coding: utf-8 -*-
"""
juni_juli_117_harga_bahan_klien.py — TERAPKAN HARGA BAHAN KLIEN KE SISTEM (13 Sep 2026).

KEPUTUSAN PEMILIK (13 Sep 2026):
  • "Terapkan semua harga bahan klien ke sistem" — harga beli bahan diambil dari
    berkas klien `HARGA BAHAN BAKU GUDANG.xlsx` (sheet Agustus), bukan angka tebakan.
  • "Harga dari klien jangan diubah" — skrip ini **TIDAK menyentuh `list_price`**
    (harga jual) sama sekali, dan tidak menyentuh menu/pricelist/order.

Latar belakang:
  `scripts/juni_juli_68_hpp_harga_asli.py` sudah membaca berkas ini, TETAPI skrip itu
  READ-ONLY — harga asli klien hanya dipakai untuk hitungan sementara, tidak pernah
  ditulis ke `standard_price`. Akibatnya sistem masih memakai harga lama.

LINGKUP (sengaja sempit & aman) — hanya kategori bahan resep:
  `Bahan Baku Food` · `Bahan Baku Beverage` · `Bahan Pendukung Menu`  (semua FIFO)
  + allow-list barang jual-langsung yang biayanya memang dari berkas bahan klien:
  `AIR GELAS` (→ "Air Mineral Gelas").
  Produk kategori lain (Barang Perlengkapan Operasional dsb.) TIDAK disentuh —
  tidak memengaruhi HPP menu.

AMAN DARI JURNAL/REVALUASI:
  Produk FIFO dilewati oleh `_change_standard_price` (stock_account/models/product.py),
  jadi menulis `standard_price` **tidak** membuat `product.value` / jurnal revaluasi.
  Kategori di atas semuanya FIFO. order & stok historis tidak disentuh.

PENGECUALIAN YANG DISENGAJA (tidak ditulis):
  * `AYAM CUT 2` — berkas klien memakai satuan **@1 Ekor** (38.618,63). Sistem memakai
    **PTG**, dan 1 PTG = ½ ekor → 19.309,32. Angka sistem sudah BENAR; jangan digandakan.
  * `MIKA BUNDAR` ↔ klien "Mika Burger" 390 — nama beda (bundar vs burger), TIDAK
    dijalankan kecuali `INCLUDE_DUGAAAN=1`.

  dry-run : su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_117_harga_bahan_klien.py
  eksekusi: su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 --no-http \
            --db_host db --db_port 5432 --db_user odoo --db_password odoo" \
            < scripts/juni_juli_117_harga_bahan_klien.py
"""
import os
import re

import openpyxl

RUN = os.environ.get("RUN") == "1"
INCLUDE_DUGAAAN = os.environ.get("INCLUDE_DUGAAAN") == "1"
XLSX = os.environ.get("XLSX") or next(
    (p for p in ("product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx",
                 "../product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx",
                 "/root/odoo/product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx")
     if os.path.exists(p)), None)

# kategori yang boleh disentuh (semua FIFO → tanpa revaluasi)
KATEGORI = ("Bahan Baku Food", "Bahan Baku Beverage", "Bahan Pendukung Menu")
# barang jual-langsung yang biayanya dari berkas bahan klien
ALLOW_JUAL = {"AIR GELAS": "AIR MINERAL GELAS"}
# alias nama sistem -> nama di berkas klien (HANYA yang sudah diverifikasi)
ALIAS = {
    "BUBUK LEMON TEA": "LEMON TEA",
    "AIR GELAS": "AIR MINERAL GELAS",
    "KEMASAN SEGEPOK": "KEMASAN SEGEPOK (BIASA)",
    "PLASTIK KLIP 8X5": "PLASTIK KLIP 5X8",
}
# nama yang sengaja DILEWATI, beserta alasannya
LEWATI = {
    "AYAM CUT 2": "satuan klien @1 Ekor; sistem pakai PTG (1 PTG = 1/2 ekor) → 19.309,32 sudah benar",
}
# nama yang butuh konfirmasi dulu (nama tidak identik)
DUGAAAN = {"MIKA BUNDAR": "MIKA BURGER"}

cr = env.cr
PT = env["product.template"]
PP = env["product.product"]

say = lambda m="": print(m)
money = lambda x: "{:>14,.2f}".format(float(x or 0))


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def std_price(pp_id):
    cr.execute("SELECT (standard_price->>'1')::numeric FROM product_product WHERE id=%s", (pp_id,))
    r = cr.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


def hpp_of(tmpl_id):
    """HPP dari resep: jumlah(qty komponen x harga beli). 0 kalau tanpa resep."""
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tmpl_id,))
    return float(cr.fetchone()[0] or 0)


# ================================================================ 1. BACA BERKAS KLIEN
if not XLSX:
    raise SystemExit("!! berkas HARGA BAHAN BAKU GUDANG.xlsx tidak ditemukan")

wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
wb.close()
hi = next(i for i, r in enumerate(rows[:8]) if any((c or "") == "Nama Barang" for c in r))
hdr = [("" if c is None else str(c).strip()) for c in rows[hi]]
i_nama = hdr.index("Nama Barang")
i_sat = hdr.index("Satuan")
i_kecil = next(j for j, h in enumerate(hdr) if h.upper().startswith("HRG/SAT"))

klien = {}
for r in rows[hi + 1:]:
    cells = list(r) + [None] * 8
    if not cells[i_nama]:
        continue
    try:
        v = float(cells[i_kecil])
    except (TypeError, ValueError):
        continue
    klien[norm(cells[i_nama])] = (str(cells[i_nama]).strip(), v, str(cells[i_sat] or ""))

say("=" * 120)
say("TERAPKAN HARGA BAHAN KLIEN KE SISTEM   |   RUN=%s   DUGAAAN=%s" % (RUN, INCLUDE_DUGAAAN))
say("=" * 120)
say("berkas : %s" % XLSX)
say("sheet  : %s   |   bahan terbaca: %d" % (ws.title if hasattr(ws, "title") else "-", len(klien)))

# ================================================================ 2. SUSUN RENCANA
cr.execute("""
    SELECT pp.id, pt.id, (pt.name->>'en_US'), COALESCE(pc.name, ''), (uu.name->>'en_US'),
           COALESCE((pp.standard_price->>'1')::numeric, 0), pt.available_in_pos
      FROM product_product pp
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
      LEFT JOIN product_category pc ON pc.id = pt.categ_id
      LEFT JOIN uom_uom uu ON uu.id = pt.uom_id
     WHERE pp.active AND pt.active
     ORDER BY 1
""")
semua = cr.fetchall()
wb_map = {norm(r[2]): r for r in semua}

ubah, sama, dilewati, takada, dugaan, luar = [], [], [], [], [], []
for pp_id, tmpl_id, nama, kat, uom, sp, in_pos in semua:
    dalam_lingkup = kat in KATEGORI or nama.upper() in ALLOW_JUAL
    if not dalam_lingkup:
        luar.append((nama, kat, sp))
        continue
    k = norm(nama)
    hit = klien.get(k) or klien.get(norm(ALIAS.get(nama.upper(), "")))
    if not hit and nama.upper() in DUGAAAN:
        hit = klien.get(norm(DUGAAAN[nama.upper()]))
        if hit and not INCLUDE_DUGAAAN:
            dugaan.append((nama, kat, sp, hit))
            continue
    if not hit:
        takada.append((nama, kat, sp))
        continue
    if nama.upper() in LEWATI:
        dilewati.append((nama, sp, hit, LEWATI[nama.upper()]))
        continue
    nm_klien, harga_klien, sat_klien = hit
    if abs(harga_klien - float(sp)) < 0.005:
        sama.append((nama, kat, sp, sat_klien))
    else:
        ubah.append((pp_id, tmpl_id, nama, kat, uom, float(sp), harga_klien, sat_klien, in_pos))

say("")
say("[A. AKAN DIUBAH] %d bahan" % len(ubah))
say("   %-30s %-24s %14s %14s %16s" % ("bahan", "kategori", "sekarang", "menjadi", "satuan beli klien"))
say("   " + "-" * 104)
for pp_id, tmpl_id, nama, kat, uom, sp, kk, sat, in_pos in sorted(ubah, key=lambda x: -abs(x[6] - x[5])):
    pct = ((kk - sp) / sp * 100) if sp else 0
    say("   %-30s %-24s %s %s  %+7.1f%%  %s" % (nama[:29], kat[:23], money(sp), money(kk), pct, sat[:16]))

say("")
say("[B. SUDAH COCOK — tidak diubah] %d bahan" % len(sama))
for nama, kat, sp, sat in sama:
    say("   %-30s %s  %s" % (nama[:29], money(sp), sat[:16]))

say("")
say("[C. DILEWATI SENGAJA] %d bahan" % len(dilewati))
for nama, sp, hit, alasan in dilewati:
    say("   %-30s sistem=%s  klien=%s" % (nama[:29], money(sp), money(hit[1])))
    say("      → %s" % alasan)

if dugaan:
    say("")
    say("[D. BUTUH KONFIRMASI (nama tidak identik)] %d bahan" % len(dugaan))
    for nama, kat, sp, hit in dugaan:
        say("   %-30s sistem=%s  '%s'=%s  (nama beda)" % (nama[:29], money(sp), hit[0], money(hit[1])))
    say("      → jalankan dengan INCLUDE_DUGAAAN=1 bila Anda pastikan itemnya sama.")

say("")
say("[E. BELUM ADA HARGA DI BERKAS KLIEN — angka kita yang dipakai] %d bahan" % len(takada))
for nama, kat, sp in takada:
    say("   %-30s %-24s %s" % (nama[:29], kat[:23], money(sp)))

# ================================================================ 3. DAMPAK KE HPP MENU
terdampak = {}
for pp_id, tmpl_id, nama, kat, uom, sp, kk, sat, in_pos in ubah:
    cr.execute("""
        SELECT DISTINCT b.product_tmpl_id
          FROM mrp_bom_line bl JOIN mrp_bom b ON b.id = bl.bom_id
         WHERE bl.product_id = %s AND b.active
    """, (pp_id,))
    for (tid,) in cr.fetchall():
        terdampak.setdefault(tid, [])
        if nama not in terdampak[tid]:
            terdampak[tid].append(nama)

say("")
say("[F. DAMPAK HPP MENU] %d resep memakai bahan yang diubah" % len(terdampak))
say("   %-46s %14s %14s %14s" % ("menu", "HPP sekarang", "HPP sesudah", "selisih"))
say("   " + "-" * 92)
skrg, sdhl = {}, {}
for tid, bahan in sorted(terdampak.items()):
    h0 = hpp_of(tid)
    skrg[tid] = h0
    # hitung HPP sesudah dengan harga baru (tanpa menulis apa pun)
    cr.execute("""
        SELECT COALESCE(SUM(bl.product_qty * COALESCE((cp.standard_price->>'1')::numeric, 0)), 0)
          FROM mrp_bom b JOIN mrp_bom_line bl ON bl.bom_id = b.id
          LEFT JOIN product_product cp ON cp.id = bl.product_id
         WHERE b.product_tmpl_id = %s AND b.active
    """, (tid,))
    h1 = float(cr.fetchone()[0] or 0)
    for pp_id, tmpl_id, nama, kat, uom, sp, kk, sat, in_pos in ubah:
        cr.execute("""
            SELECT COALESCE(SUM(bl.product_qty), 0)
              FROM mrp_bom_line bl JOIN mrp_bom b ON b.id = bl.bom_id
             WHERE bl.product_id = %s AND b.product_tmpl_id = %s AND b.active
        """, (pp_id, tid))
        q = float(cr.fetchone()[0] or 0)
        if q:
            h1 += q * (kk - sp)
    sdhl[tid] = h1
    t = PT.browse(tid)
    say("   %-46s %s %s  %+13.2f" % (t.display_name[:45], money(h0), money(h1), h1 - h0))

if not RUN:
    say("")
    say("DRY-RUN — tidak ada perubahan di DB. Jalankan RUN=1 untuk eksekusi.")
    say("=" * 120)
    env.cr.rollback()
    raise SystemExit(0)

# ================================================================ 4. EKSEKUSI
say("")
say("[EKSEKUSI]")
for pp_id, tmpl_id, nama, kat, uom, sp, kk, sat, in_pos in ubah:
    p = PP.browse(pp_id)
    p.with_context(disable_auto_revaluation=True).standard_price = kk
    say("   %-30s %s → %s" % (nama[:29], money(sp), money(kk)))
env.cr.flush()
env.cr.commit()
say("   [COMMITTED] %d bahan" % len(ubah))

# ================================================================ 5. VERIFIKASI
say("")
say("=" * 120)
say("[VERIFIKASI]")
salah = 0
for pp_id, tmpl_id, nama, kat, uom, sp, kk, sat, in_pos in ubah:
    if abs(std_price(pp_id) - kk) > 0.005:
        salah += 1
        say("   !! %s masih %s (seharusnya %s)" % (nama, money(std_price(pp_id)), money(kk)))
say("   bahan yang tidak sesuai target : %d" % salah)
say("")
say("   HPP menu terdampak (sekarang → sebelumnya):")
for tid, bahan in sorted(terdampak.items()):
    t = PT.browse(tid)
    say("      %-44s %s → %s   %+13.2f" % (t.display_name[:43], money(hpp_of(tid)),
                                            money(skrg[tid]), hpp_of(tid) - skrg[tid]))
say("")
say("   harga jual tidak disentuh:")
cr.execute("SELECT COUNT(*) FROM product_template WHERE active")
say("      total produk aktif : %d" % cr.fetchone()[0])
say("      (list_price tidak diubah oleh skrip ini — halaman ini hanya untuk konfirmasi)")
say("=" * 120)
