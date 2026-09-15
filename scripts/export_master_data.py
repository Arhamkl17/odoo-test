# -*- coding: utf-8 -*-
"""Ekspor tabel master + transaksi ke CSV (di dalam `odoo shell`, baca-saja).

Tujuan: menyediakan salinan **terbaca manusia** dari master data (produk, BOM,
harga, COA, vendor, konfigurasi POS) dan transaksi (order POS, jurnal, stok)
sebagai pelengkap dump database — berguna saat audit, atau bila perlu impor
ulang tanpa memulihkan dump penuh.

Pemakaian:
  MASTER_DIR=/path/keluaran su odoo -s /bin/bash -c "odoo shell -d Test1 ..." \
    < scripts/export_master_data.py

Catatan versi: nama tabel diambil dari ORM (`model._table`) sehingga tidak
perlu menebak skema (Odoo 19 mengganti beberapa nama, mis. kategori UoM).
Model yang tidak terpasang dilewati dan dicatat di `_CATATAN.csv`.
"""
import csv
import os

env = env  # noqa: F821 (disediakan odoo shell)

OUT = os.environ.get("MASTER_DIR") or "/tmp/odoo_master_export"
os.makedirs(OUT, exist_ok=True)

# (model, keterangan) — urutan mengikuti alur: master dulu, transaksi kemudian
TABLES = [
    # -- identitas & akuntansi dasar
    ("res.company", "master"),
    ("res.partner", "master-pihak"),
    ("res.currency", "master"),
    ("res.bank", "master"),
    ("account.account", "master-COA"),
    ("account.journal", "master-jurnal"),
    ("account.tax", "master-pajak"),
    ("account.tax.repartition.line", "master-pajak"),
    ("account.asset", "master-aset"),
    ("account.asset.profile", "master-aset"),
    # -- produk, satuan, harga
    ("product.category", "master-produk"),
    ("product.uom", "master-uom"),
    ("uom.uom", "master-uom"),
    ("product.template", "master-produk"),
    ("product.product", "master-produk"),
    ("product.supplierinfo", "master-vendor"),
    ("product.pricelist", "master-harga"),
    ("product.pricelist.item", "master-harga"),
    # -- resep / bill of materials
    ("mrp.bom", "master-bom"),
    ("mrp.bom.line", "master-bom"),
    ("mrp.bom.byproduct", "master-bom"),
    # -- stok & gudang
    ("stock.warehouse", "master-gudang"),
    ("stock.location", "master-gudang"),
    ("stock.quant", "transaksi-stok"),
    ("stock.move", "transaksi-stok"),
    ("stock.move.line", "transaksi-stok"),
    ("stock.picking", "transaksi-stok"),
    ("stock.picking.type", "master-gudang"),
    # -- POS
    ("pos.config", "master-pos"),
    ("pos.payment.method", "master-pos"),
    ("pos.category", "master-pos"),
    ("pos.session", "transaksi-pos"),
    ("pos.order", "transaksi-pos"),
    ("pos.order.line", "transaksi-pos"),
    ("pos.payment", "transaksi-pos"),
    # -- jurnal & buku besar
    ("account.move", "transaksi-jurnal"),
    ("account.move.line", "transaksi-jurnal"),
    ("account.partial.reconcile", "transaksi-jurnal"),
    # -- penomoran & modul
    ("ir.sequence", "master-penomoran"),
    ("ir.sequence.date_range", "master-penomoran"),
    ("ir.module.module", "master-modul"),
    # -- pelaporan MIS (buatan proyek)
    ("mis.report", "master-laporan"),
    ("mis.report.kpi", "master-laporan"),
    ("mis.report.instance", "master-laporan"),
    ("mis.report.instance.period", "master-laporan"),
]

notes = []
summary = []
models = env.registry.models.keys()

for model_name, group in TABLES:
    if model_name not in models:
        notes.append("%s|model tidak ada di versi Odoo ini (dilewati)" % model_name)
        continue
    model = env[model_name].with_context(active_test=False)
    table = model._table
    fname = "%s.csv" % model_name.replace(".", "_")
    path = os.path.join(OUT, fname)
    try:
        env.cr.execute('SELECT count(*) FROM "%s"' % table)
        (count,) = env.cr.fetchone()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            env.cr.copy_expert('COPY (SELECT * FROM "%s") TO STDOUT WITH CSV HEADER' % table, fh)
        summary.append((group, model_name, table, count))
        print("EXPORT|%s|%s|%s|%d baris" % (group, model_name, table, count))
    except Exception as exc:  # noqa: BLE001 — lanjutkan ekspor meski satu tabel gagal
        notes.append("%s|GAGAL: %s" % (model_name, exc))
        print("EXPORT-FAIL|%s|%s" % (model_name, exc))

# ringkasan + catatan
with open(os.path.join(OUT, "_RINGKASAN.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["grup", "model", "tabel", "jumlah_baris", "berkas"])
    for group, model_name, table, count in summary:
        w.writerow([group, model_name, table, count, "%s.csv" % model_name.replace(".", "_")])

with open(os.path.join(OUT, "_CATATAN.csv"), "w", newline="", encoding="utf-8") as fh:
    fh.write("model|catatan\n")
    for line in notes:
        fh.write(line + "\n")

print("MASTER_EXPORT_DONE|%d tabel|%d catatan|%s" % (len(summary), len(notes), OUT))
