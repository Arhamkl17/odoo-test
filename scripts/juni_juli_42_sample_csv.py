# -*- coding: utf-8 -*-
"""Utilitas sementara: bikin CSV contoh isian klien dari TEMPLATE (host python3)."""
import csv
import io
import sys

SRC = "import_data/harga_beli_klien_TEMPLATE.csv"
DST = "import_data/harga_beli_klien_CONTOH.csv"
FACTOR = float(sys.argv[1]) if len(sys.argv) > 1 else 0.63

with io.open(SRC, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

for i, r in enumerate(rows):
    old = float(r["harga_sistem_sekarang_rp"])
    # baris terakhir: sengaja DIBIARKAN KOSONG (uji isian sebagian)
    if i == len(rows) - 1:
        continue
    # baris ke-3: harga per satuan beli + isi (uji jalur pembagian)
    if i == 2:
        r["isi_per_satuan_beli"] = "20000"
        r["harga_per_satuan_beli_rp"] = "%.4f" % (old * FACTOR * 20000)
        continue
    # baris ke-5: sengaja ekstrem (uji penolakan)
    if i == 4:
        r["harga_per_satuan_kecil_rp"] = "%.4f" % (old * 100)
        continue
    # baris ke-7: harga 0 (uji penolakan)
    if i == 6:
        r["harga_per_satuan_kecil_rp"] = "0"
        continue
    r["harga_per_satuan_kecil_rp"] = "%.4f" % (old * FACTOR)
    r["catatan"] = "contoh"

# tambah 1 baris DUPLIKAT (uji deteksi)
rows.append(dict(rows[0]))
# tambah 1 baris product_id ngawur (uji unknown id)
bad = dict(rows[1])
bad["product_id"] = "999999"
rows.append(bad)

with io.open(DST, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("ditulis %s (%d baris, faktor %.2f)" % (DST, len(rows), FACTOR))
