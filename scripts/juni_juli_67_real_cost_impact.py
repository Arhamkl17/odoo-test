# -*- coding: utf-8 -*-
"""
juni_juli_67_real_cost_impact.py — DAMPAK HARGA BAHAN ASLI KLIEN (read-only, tanpa Odoo).

Sumber: product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx (sheet 'Agustus')
        kolom: Nama Barang | Satuan | Harga | Isi | HRG/SAT KECIL
Memetakan ke nama komponen, melaporkan cocok/tidak, lalu menghitung harga per komponen.
"""
import os
import re
from collections import defaultdict

import openpyxl

PATH = "product_photos/data sheet master/HARGA BAHAN BAKU GUDANG.xlsx"


def norm(s):
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


wb = openpyxl.load_workbook(PATH, data_only=True, read_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
wb.close()

# cari baris header
hi = None
for i, r in enumerate(rows[:8]):
    vals = [("" if c is None else str(c).strip()) for c in r]
    if "Nama Barang" in vals:
        hi = i
        break
hdr = [("" if c is None else str(c).strip()) for c in rows[hi]]
i_kode = hdr.index("Kode") if "Kode" in hdr else None
i_nama = hdr.index("Nama Barang")
i_sat = hdr.index("Satuan") if "Satuan" in hdr else None
i_harga = hdr.index("Harga") if "Harga" in hdr else None
i_isi = hdr.index("Isi") if "Isi" in hdr else None
i_kecil = None
for j, h in enumerate(hdr):
    if h.upper().startswith("HRG/SAT"):
        i_kecil = j
        break

print("header:", hdr)
print("index: nama=%s sat=%s harga=%s isi=%s kecil=%s" % (
    i_nama, i_sat, i_harga, i_isi, i_kecil))
print("")

data = []
for r in rows[hi + 1:]:
    cells = list(r) + [None] * 8
    nm = cells[i_nama]
    if not nm:
        continue
    kecil = cells[i_kecil]
    try:
        kecil_f = float(kecil)
    except (TypeError, ValueError):
        kecil_f = None
    data.append({
        "kode": cells[i_kode] if i_kode is not None else "",
        "nama": str(nm).strip(),
        "satuan": str(cells[i_sat] or "").strip() if i_sat is not None else "",
        "harga": cells[i_harga],
        "isi": str(cells[i_isi] or "").strip() if i_isi is not None else "",
        "kecil": kecil_f,
        "kecil_raw": kecil,
    })

print("=" * 116)
print("HARGA BAHAN BAKU KLIEN — %d baris" % len(data))
print("=" * 116)
by_norm = {}
for d in data:
    by_norm.setdefault(norm(d["nama"]), d)

ok = [d for d in data if d["kecil"] is not None]
tidakhitung = [d for d in data if d["kecil"] is None]
print("  punya harga per satuan kecil : %d" % len(ok))
print("  'TIDAK DIHITUNG' / kosong    : %d" % len(tidakhitung))
print("")
print("%-34s %-16s %12s %-14s %12s" % ("nama barang", "satuan beli", "harga beli", "isi", "per satuan kecil"))
print("-" * 116)
for d in data:
    if d["kecil"] is None:
        continue
    print("%-34s %-16s %12s %-14s %12s" % (
        d["nama"][:34], d["satuan"][:16],
        ("{:,.0f}".format(d["harga"]) if isinstance(d["harga"], (int, float)) else str(d["harga"])[:12]),
        d["isi"][:14], "{:,.4f}".format(d["kecil"])))
print("-" * 116)
print("")
print("BARIS TANPA HARGA PER SATUAN KECIL (%d):" % len(tidakhitung))
for d in tidakhitung:
    print("   %-40s %-16s %s" % (d["nama"][:40], d["satuan"][:16], d["kecil_raw"]))
