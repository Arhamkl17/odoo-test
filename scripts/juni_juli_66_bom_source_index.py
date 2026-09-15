# -*- coding: utf-8 -*-
"""
juni_juli_66_bom_source_index.py — INDEKS BOM dari berkas sumber klien (tanpa Odoo).

Memetakan kolom berdasarkan NAMA HEADER (bukan posisi), karena tiap sheet beda layout.
Mengeluarkan kolom `ID Eksternal` = pengenal produk di Odoo klien, lalu dicocokkan dengan
ekspor produk klien `import_data/csv/05_products_with_id.csv`.

Tujuan: membedakan
  - nama beda, ID Eksternal SAMA  -> sebenarnya PRODUK YANG SAMA (importer salah cocokkan)
  - nama sama, ID Eksternal beda  -> memang dua produk berbeda
"""
import csv
import io
import os
from collections import defaultdict, OrderedDict

import openpyxl

DIR = "product_photos/data sheet master"
SRC = ["mrp_bom Barang Combo.xlsx", "mrp_bom FIX - PALLANGGA.xlsx"]
HDR_KEYS = ("Produk", "Kuantitas", "Jenis BoM", "Baris BoM/Komponen",
            "Baris BoM/Kuantitas", "Baris BoM/Unit", "ID Eksternal", "Unit")


def header_index(cells):
    """Kembalikan dict nama kolom -> index bila baris ini baris header."""
    got = {}
    for i, c in enumerate(cells):
        if c in HDR_KEYS:
            got.setdefault(c, i)
    return got if "Produk" in got and "Baris BoM/Komponen" in got else None


index = OrderedDict()      # nama -> {ext_ids, n_lines, sheets}
by_ext = defaultdict(set)  # ext_id -> {nama}

for fn in SRC:
    path = os.path.join(DIR, fn)
    if not os.path.exists(path):
        continue
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        cur, H, used = None, None, 0
        for r in ws.iter_rows(values_only=True):
            cells = [("" if c is None else str(c).strip()) for c in r]
            if not any(cells):
                continue
            if H is None:
                H = header_index(cells)
                continue
            prod = cells[H["Produk"]] if H.get("Produk") is not None and H["Produk"] < len(cells) else ""
            comp = cells[H["Baris BoM/Komponen"]] if H.get("Baris BoM/Komponen") is not None and H["Baris BoM/Komponen"] < len(cells) else ""
            ext = cells[H["ID Eksternal"]] if H.get("ID Eksternal") is not None and H["ID Eksternal"] < len(cells) else ""
            if prod:
                cur = prod.upper()
                rec = index.setdefault(cur, {"ext_ids": set(), "n_lines": 0, "sheets": set()})
                rec["n_lines"] += 1
                rec["sheets"].add(ws.title)
                if ext:
                    rec["ext_ids"].add(ext)
                    by_ext[ext].add(cur)
                used += 1
            elif cur and comp:
                index[cur]["n_lines"] += 1
                used += 1
            if used > 4000:
                break
    wb.close()

# ekspor produk klien: ext_id -> nama
klien_ext = {}
klien_nama = {}
with io.open("import_data/csv/05_products_with_id.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        nm = (r.get("Nama") or "").strip().upper()
        ext = (r.get("ID Eksternal") or "").strip()
        if nm:
            klien_nama[nm] = ext
            if ext:
                klien_ext[ext] = nm

print("=" * 122)
print("INDEKS BOM SUMBER KLIEN — %d nama produk" % len(index))
print("=" * 122)
print("%-52s %6s %-4s %s" % ("produk", "baris", "ext", "sheet"))
print("-" * 122)
for nm, rec in sorted(index.items()):
    print("%-52s %6d %-4s %s" % (
        nm[:52], rec["n_lines"], len(rec["ext_ids"]) if rec["ext_ids"] else "-",
        ",".join(sorted(rec["sheets"]))[:40]))

print("")
print("=" * 122)
print("A. NAMA BEDA, ID EKSTERNAL SAMA  -> SEBENARNYA PRODUK YANG SAMA")
print("=" * 122)
n = 0
for ext, names in sorted(by_ext.items()):
    if len(names) > 1:
        n += 1
        print("   %s" % ext)
        for x in sorted(names):
            print("        - %s" % x)
if not n:
    print("   (tidak ada)")

print("")
print("=" * 122)
print("B. ID EKSTERNAL YANG DIPAKAI BOM vs NAMA PRODUK DI EKSPOR KLIEN")
print("=" * 122)
cocok = beda = 0
for ext, names in sorted(by_ext.items()):
    kn = klien_ext.get(ext)
    nm_bom = sorted(names)
    if kn:
        cocok += 1
        flag = "OK" if kn in [x.upper() for x in nm_bom] else "!! NAMA BEDA"
        print("   %-56s bom=%-40s klien=%-40s %s" % (ext[-28:], "|".join(nm_bom)[:40], kn[:40], flag))
    else:
        beda += 1
        print("   %-56s bom=%-40s klien=%s" % (ext[-28:], "|".join(nm_bom)[:40], "(ID tidak ada di ekspor)"))
print("   %d ID cocok, %d ID tidak ditemukan di ekspor produk" % (cocok, beda))

print("")
print("=" * 122)
print("C. PENCARIAN KHUSUS — pasangan yang jadi sengketa")
print("=" * 122)
CARIK = ["PKG SAMBAL KOREK SURABAYA", "PKG SAMBAL IJO PADANG", "PKG SAMBAL RICA MANADO",
         "PAKET MEVVAH BERDUA", "PKG MEVVAH", "PKG GEPREK MEVVAH", "BIG HEMAT 4",
         "PAKET KULIT CRISPY", "PAKET AYAM CRISPY", "YUKSSS RAMA", "PKG LOKAL DUO",
         "SEGEPOK BERLIMA", "PAKET SETIA"]
for c in CARIK:
    hits = [(nm, rec) for nm, rec in index.items() if c in nm]
    print("")
    print("   >> '%s' -> %d nama di berkas BOM" % (c, len(hits)))
    for nm, rec in sorted(hits):
        exts = sorted(rec["ext_ids"])
        print("      %-52s %3d baris  ext=%s" % (
            nm[:52], rec["n_lines"], exts[0][-26:] if exts else "-"))
    # apakah nama ini ada di ekspor produk klien?
    if c.upper() in klien_nama:
        print("      [ekspor produk klien] '%s' ext=%s" % (c, klien_nama[c.upper()][-26:] or "-"))
