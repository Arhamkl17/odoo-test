# -*- coding: utf-8 -*-
"""
juni_juli_102_sumber_harga.py — SEMUA sumber harga dari klien (baca berkas, tidak sentuh DB).

Menjawab: kenapa ada harga Dine In, dan apakah ada daftar harga lain lagi?
"""
import csv, glob, os
import openpyxl

say = lambda m="": print(m)
say("=" * 108)
say("SEMUA SUMBER HARGA YANG DIBERIKAN KLIEN")
say("=" * 108)

say("")
say("[1] TEMPLATE IMPORT HARGA DINE IN.xlsx")
say("")
wb = openpyxl.load_workbook("product_photos/data sheet master/TEMPLATE IMPORT HARGA DINE IN.xlsx",
                            data_only=True)
say("   jumlah sheet: %d" % len(wb.worksheets))
for ws in wb.worksheets:
    rows = list(ws.iter_rows(values_only=True))
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    say("")
    say("   ── sheet: %s   (%d baris berisi)" % (ws.title, len(rows)))
    if not rows:
        continue
    say("      header : %s" % [str(c) for c in rows[0] if c is not None])
    for r in rows[1:6]:
        say("      %s" % [str(c) if c is not None else "" for c in r])
    if len(rows) > 6:
        say("      … (%d baris lain)" % (len(rows) - 6))
wb.close()

say("")
say("[2] 06_price_update.csv  — daftar harga standar")
say("")
with open("import_data/csv/06_price_update.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
say("   %d baris | kolom: %s" % (len(rows), list(rows[0].keys())))
for r in rows[:8]:
    say("      %-58s %-10s %s" % ((r.get("Nama") or "")[:58], r.get("Harga Jual"), r.get("Unit")))
say("      … (%d baris lain)" % max(len(rows) - 8, 0))

say("")
say("[3] 05_products_with_id.csv  — kolom harga yang ADA nilainya")
say("")
with open("import_data/csv/05_products_with_id.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
ada = [r for r in rows if (r.get("Harga Jual") or "").strip() not in ("", "0", "1")]
say("   %d baris produk | dengan Harga Jual bermakna: %d" % (len(rows), len(ada)))
for r in ada[:8]:
    say("      %-58s %s" % ((r.get("Nama") or "")[:58], r.get("Harga Jual")))
say("      → sisanya bernilai 0 atau 1 (klien belum mengisi harga)")

say("")
say("[4] Semua berkas lain yang mungkin memuat harga")
say("")
pola = ["*harga*", "*HARGA*", "*price*", "*pricelist*", "*Pricelist*"]
seen = set()
for p in pola:
    for path in glob.glob(p) + glob.glob("**/" + p, recursive=True):
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            size = os.path.getsize(path) / 1024.0
            say("   %-72s %8.1f KB" % (path, size))

say("")
say("[5] Ekspor pricelist milik klien (kalau ada)")
say("")
for path in sorted(glob.glob("**/*ricelist*", recursive=True)):
    if os.path.isfile(path) and path.endswith((".xlsx", ".csv")):
        say("   %s" % path)

say("")
say("=" * 108)
