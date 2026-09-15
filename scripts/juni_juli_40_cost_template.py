# -*- coding: utf-8 -*-
"""
juni_juli_40_cost_template.py — buat TEMPLATE isian harga beli untuk klien.

READ-ONLY terhadap Odoo. Menulis 1 file CSV:
    import_data/harga_beli_klien_TEMPLATE.csv

Daftar komponen = semua DAUN BOM (komponen tanpa BOM sendiri) yang benar-benar
terpakai di order POS Juni–Agustus. Kolom "harga_per_satuan_kecil_rp" yang diisi
klien -> dibaca oleh `scripts/juni_juli_41_cost_import.py`.

Struktur kolom:
  product_id                 kunci — ID `product.product` (varian), JANGAN diubah
  nama_komponen              untuk dibaca manusia saja
  referensi_internal         default_code di sistem
  uom_pakai                  satuan yang dipakai resep (harga harus per satuan INI)
  satuan_beli_klien          istilah klien dari ekspor (mis. "BKS @9PTG") — informasi
  isi_per_satuan_beli        isi 1 satuan beli dalam satuan pakai (diisi bila klien
                             memilih mengisi harga per satuan beli)
  harga_per_satuan_beli_rp   (opsional) harga per satuan beli
  harga_per_satuan_kecil_rp  >>> YANG INI DIISI KLIEN <<< harga per uom_pakai
  harga_sistem_sekarang_rp   pembanding (isian agent lama, bukan data klien)
  pemakaian_3_bulan          qty terpakai Juni–Agustus 2026 (satuan pakai)
  nilai_sistem_3_bulan_rp    pemakaian × harga sistem sekarang
  catatan                    bebas
"""
import io
import csv
import os
from collections import defaultdict

cr = env.cr
Bom = env["mrp.bom"]
Prod = env["product.product"]
AM = env["account.move"]
OUT = "import_data/harga_beli_klien_TEMPLATE.csv"
KLIEN_CSV = "import_data/csv/05_bahan_with_id.csv"
say = lambda m="": print(m)

say("=" * 100)
say("TEMPLATE HARGA BELI KLIEN")
say("=" * 100)

# --- 1. pemakaian aktual per komponen dari stock move konsumsi -------------
# Move konsumsi dibuat generator HPP: origin "HPP-BOM konsumsi <Bulan> <kode>".
cr.execute("""
    SELECT sm.product_id, SUM(sm.quantity)
      FROM stock_move sm
     WHERE sm.state='done' AND sm.origin LIKE 'HPP-BOM konsumsi%%'
     GROUP BY 1""")
usage = {int(pid): float(q or 0) for pid, q in cr.fetchall()}

# nilai HPP aktual per bulan (untuk laporan), dihitung dari JE
cr.execute("""
    SELECT to_char(am.date,'YYYY-MM') m, aa.code_store->>'1' code, SUM(aml.balance)
      FROM account_move_line aml JOIN account_move am ON am.id=aml.move_id
      JOIN account_account aa ON aa.id=aml.account_id
     WHERE am.state='posted' AND aa.account_type='expense_direct_cost'
     GROUP BY 1,2 ORDER BY 1,2""")
say("")
say("HPP aktual per bulan (kontrol):")
hpp_month = defaultdict(float)
for m, code, v in cr.fetchall():
    hpp_month[m] += float(v)
for m in sorted(hpp_month):
    say("   %s  HPP = %18s" % (m, "{:,.2f}".format(hpp_month[m])))

# --- 2. satuan beli dari ekspor klien (informasi saja) --------------------
beli = {}
if os.path.exists(KLIEN_CSV):
    with io.open(KLIEN_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            beli[(r.get("Nama") or "").strip().upper()] = (r.get("Unit Pembelian") or "").strip()

# --- 3. susun baris -------------------------------------------------------
rows = []
for pid, q in usage.items():
    p = Prod.browse(pid)
    if not p.exists():
        continue
    tmpl = p.product_tmpl_id
    sp = p.standard_price
    sp = sp.get("1") if isinstance(sp, dict) else sp
    sp = float(sp or 0.0)
    rows.append({
        "product_id": pid,
        "nama_komponen": p.display_name,
        "referensi_internal": p.default_code or "",
        "uom_pakai": p.uom_id.name,
        "satuan_beli_klien": beli.get((p.display_name or "").upper(), ""),
        "isi_per_satuan_beli": "",
        "harga_per_satuan_beli_rp": "",
        "harga_per_satuan_kecil_rp": "",
        "harga_sistem_sekarang_rp": "%.4f" % sp,
        "pemakaian_3_bulan": "%.4f" % q,
        "nilai_sistem_3_bulan_rp": "%.2f" % (sp * q),
        "catatan": "",
    })
rows.sort(key=lambda r: -float(r["nilai_sistem_3_bulan_rp"]))

FIELDS = ["product_id", "nama_komponen", "referensi_internal", "uom_pakai",
          "satuan_beli_klien", "isi_per_satuan_beli", "harga_per_satuan_beli_rp",
          "harga_per_satuan_kecil_rp", "harga_sistem_sekarang_rp",
          "pemakaian_3_bulan", "nilai_sistem_3_bulan_rp", "catatan"]

with io.open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow(r)

tot = sum(float(r["nilai_sistem_3_bulan_rp"]) for r in rows)
say("")
say("Ditulis: %s" % OUT)
say("   komponen          : %d" % len(rows))
say("   total biaya sistem: %s  (3 bulan)" % "{:,.2f}".format(tot))
say("   kolom diisi klien : harga_per_satuan_kecil_rp")
say("                       (atau harga_per_satuan_beli_rp + isi_per_satuan_beli)")
say("")
say("10 komponen terbesar:")
for r in rows[:10]:
    say("   %-32s %-6s sistem=%12s  pakai=%14s %s" % (
        r["nama_komponen"][:32], r["uom_pakai"], r["harga_sistem_sekarang_rp"],
        r["pemakaian_3_bulan"], r["uom_pakai"]))
say("=" * 100)
env.cr.rollback()
