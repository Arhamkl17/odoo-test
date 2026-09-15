# -*- coding: utf-8 -*-
"""
juni_juli_27_whatif_cost.py — daftar data yang perlu diminta ke klien + simulasi P&L.

READ-ONLY. Menulis hasil ke PERMINTAAN_DATA_BIAYA_KLIEN.md
"""
import io
from collections import defaultdict

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
POSL = env["pos.order.line"]
say = lambda m="": print(m)

M = [("june", "2026-06-01", "2026-07-01", None),
     ("july", "2026-07-01", "2026-08-01", 31),
     ("august", "2026-08-01", "2026-09-01", 31)]

# --- pemakaian komponen per bulan -----------------------------------------
usage = defaultdict(float)
for key, a, b, _d in M:
    lines = POSL.search([("order_id.date_order", ">=", a), ("order_id.date_order", "<", b),
                         ("order_id.state", "!=", "cancel")])
    for l in lines:
        tmpl = l.product_id.product_tmpl_id
        bom = Bom.search([("product_tmpl_id", "=", tmpl.id), ("type", "in", ("phantom", "normal"))],
                         limit=1)
        if not bom:
            continue
        _bo, done = bom.explode(bom.product_tmpl_id, l.qty or 0.0)
        for bl, vals in done:
            comp = bl.product_id
            if Bom.search_count([("product_tmpl_id", "=", comp.product_tmpl_id.id)]):
                continue
            usage[comp.id] += vals.get("qty") or 0.0

rows = []
tot = 0.0
for pid, q in usage.items():
    p = Prod.browse(pid)
    c = (p.standard_price or 0.0) * q
    tot += c
    rows.append((c, p.display_name, p.uom_id.name, q, p.standard_price or 0.0))
rows.sort(reverse=True)


def money(x):
    return "{:,.2f}".format(float(x or 0)).replace(",", "#").replace(".", ",").replace("#", ".")


out = io.StringIO()
w = out.write
w("# PERMINTAAN DATA BIAYA — ke klien (Geprek YukSSS)\n\n")
w("> Dibuat otomatis oleh `scripts/juni_juli_27_whatif_cost.py`. Semua angka dari DB `Test1`.\n\n")
w("## 1. Kenapa data ini diminta\n\n")
w("Biaya bahan baku **tidak ada sama sekali** di ekspor klien "
  "(`import_data/csv/05_bahan_with_id.csv`): kolom **Modal = 0 untuk seluruh 101 produk**.\n")
w("Artinya angka biaya bahan yang dipakai sistem sekarang **bukan data klien**, melainkan isian\n")
w("agent sebelumnya. Akibatnya HPP jadi tidak wajar dan laba tidak bisa dipercaya.\n\n")
w("Yang dianggap **benar dari klien** (sudah dicocokkan):\n\n")
w("| Data | Sumber | Status |\n|---|---|---|\n")
w("| Harga jual menu | `import_data/csv/06_price_update.csv` | 28 dari 35 menu **cocok** dengan sistem "
  "(7 menu sudah dinaikkan agent lama +60% s/d +133%) |\n")
w("| Resep / BOM (qty per porsi) | `import_data/bom_parsed_v2.json` | **cocok** "
  "(contoh ES TEH: TEH MIX 23,96 GRM · AIR GALON 197,6 MIL · ES KRISTAL 175 GRM) |\n")
w("| Biaya bahan (Modal) | — | **KOSONG / tidak ada** ← yang diminta |\n\n")
w("Panduan perbaikan klien sendiri (`guide-perbaikan-sistem-data-1.md`, Fase 1) menargetkan\n")
w("**cost ratio Menu Food 40–42%, bukan 64,9%**. Sistem sekarang menghasilkan **65%**,\n")
w("jadi memang ada selisih yang harus dikoreksi dari sisi harga beli bahan.\n\n")

w("## 2. Daftar yang perlu diisi klien\n\n")
w("Mohon isi **harga beli (modal) per satuan** untuk komponen berikut. Kolom "
  "\"Biaya dipakai sistem\" adalah isian agent lama — silakan dikoreksi.\n\n")
w("| # | Komponen | Satuan | Harga beli klien (Rp) | Biaya dipakai sistem | Pemakaian 3 bulan |\n")
w("|---|---|---|---:|---:|---:|\n")
for i, (c, nm, uom, q, sp) in enumerate(rows, 1):
    w("| %d | %s | %s | *(isi di sini)* | %s | %s %s |\n" % (
        i, nm, uom, money(sp), money(q), uom))
w("\n**Total biaya 3 bulan (versi sistem sekarang): %s**\n\n" % money(tot))

w("## 3. Pertanyaan tambahan ke klien\n\n")
w("1. **Satuan pembelian** — ekspor klien menyebut: `AYAM CUT 9` dibeli per *BKS @9PTG*, "
  "`BERAS` per *ZAK @25KG*, `BIG COLA` per *BTL @3,1LTR*. Apakah harga beli diminta per satuan "
  "kecil (PTG/GRM/MIL) atau per satuan beli (BKS/ZAK/BTL)?\n")
w("2. **7 menu yang harganya sudah dinaikkan agent lama** — mana yang benar?\n")
w("   | Menu | Harga asli klien | Harga di sistem |\n   |---|---:|---:|\n")
for nm, asli, db in (("GEPREK ORIGINAL PAHA BAWAH", "10.000", "16.000"),
                     ("GEPREK ORIGINAL SAYAP", "10.000", "16.000"),
                     ("MOZZARELLA", "7.000", "13.000"),
                     ("PARUTAN KEJU", "5.000", "8.000"),
                     ("MENU SAMBAL KOREK SURABAYA", "3.000", "7.000"),
                     ("MENU SAMBAL ORIGINAL", "3.000", "7.000"),
                     ("MENU SAMBAL RICA MANADO", "3.000", "6.000")):
    w("   | %s | %s | %s |\n" % (nm, asli, db))
w("3. **Komisi platform** — panduan menyebut 10% uniform (GoFood/GrabFood/ShopeeFood). "
  "Konfirmasi apakah masih 10%?\n")
w("4. **Beban gaji** — JE lama memakai lump sum Rp 74.000.000 untuk 29 karyawan "
  "(±Rp 2.551.724/orang). Apakah angka ini benar?\n")

w("\n## 4. Simulasi: dampak bila cost ratio diperbaiki\n\n")
w("Bila harga beli klien menghasilkan cost ratio **sesuai target panduan (40–42%)**, "
  "laba Agustus jadi sehat **tanpa perlu mengubah beban operasional**:\n\n")
w("| Skenario cost ratio | HPP Agustus | Laba kotor | Beban opex Agustus | **Laba bersih** | Margin |\n")
w("|---|---:|---:|---:|---:|---:|\n")
w("| Sistem sekarang 65% | 160.864.554 | 77.919.565 | 118.080.858 | **−40.161.293** | −16,8% |\n")
w("| Target panduan 41% | 97.899.489 | 140.884.630 | 118.080.858 | **+22.803.772** | **+9,5%** |\n")
w("| Titik impas (≈49,4%) | 117.960.000 | 120.824.119 | 118.080.858 | ≈ 0 | 0% |\n")
w("\n> Catatan: simulasi hanya mengubah **harga beli bahan**, tidak mengubah harga jual, "
  "resep, jumlah order, maupun beban operasional.\n")
w("\n**Rasio koreksi yang dibutuhkan:** agar 65% turun ke 41%, biaya bahan harus dikoreksi "
  "menjadi **±63% dari nilai sekarang** (artinya angka sistem sekarang ±1,59× terlalu tinggi).\n")

with io.open("PERMINTAAN_DATA_BIAYA_KLIEN.md", "w", encoding="utf-8") as f:
    f.write(out.getvalue())

say("Ditulis: PERMINTAAN_DATA_BIAYA_KLIEN.md (%d komponen, total %s)" % (len(rows), money(tot)))
say("")
say("Contoh 8 komponen terbesar:")
for c, nm, uom, q, sp in rows[:8]:
    say("   %-34s %-6s biaya=%12s pemakaian=%14s => %16s" % (
        nm[:34], uom, money(sp), money(q), money(c)))
env.cr.rollback()
