# Ringkasan Perbaikan F7 (Parsial) — Kerapian Pricelist & Database Sisa

**Tanggal:** 15 September 2026 · **Sistem:** Odoo 19 (database `Test1`) · **Skrip:** `scripts/perbaikan_15_kerapian_f7.py` (dry-run default, `RUN=1` eksekusi)
**Status:** ✅ **Selesai untuk 2 item F7** (dari 8 item di `PLANNING_PERBAIKAN_HASIL_INSPEKSI_2026-09-15.md` §8)
**Angka keuangan:** **tidak berubah** — 58/58 metrik identik dengan baseline pra-perbaikan; 6/6 test parity `ALL PASS`

---

## 1. Ringkasan singkat

Dua hal sisa dari fase pembuatan dataset dibersihkan:

1. **Pricelist arsip `Harga Dine In` (id 4)** — sisa skenario "dine in" yang tidak jadi dipakai (103 baris harga, 0 order) → **dihapus**, dan 2 `pos.config` arsip yang menunjuknya (Dine In Pallangga/Mallengkeri) diarahkan ke `Harga Normal`.
2. **Database sisa `tmp_cost_snap` (142 MB)** — snapshot 11 Sep 2026 di server yang sama → **diarsipkan lalu dihapus**.

Tidak ada master data aktif, transaksi, jurnal, maupun laporan yang terpengaruh.

---

## 2. Item 1 — Pricelist arsip dihapus

### 2.1 Sebelum → sesudah

| | Sebelum | Sesudah |
|---|---|---|
| Pricelist aktif | `Harga Normal` (id 3, 103 item) · `Harga Platform Online` (id 5, 103 item) | sama (tidak disentuh) |
| Pricelist arsip | `Harga Dine In` (id 4, **103 item**, 0 order) | **tidak ada** (terhapus) |
| Total baris harga | 309 | **206** (−103) |
| `pos.config` id 6 & 7 (Dine In Pallangga/Mallengkeri, keduanya `active = False`, 0 order, 0 sesi) | `pricelist_id = 4` | `pricelist_id = 3` (Harga Normal) |

### 2.2 Uji rujukan sebelum menghapus (agar tidak ada yang rusak)

Pemindaian dilakukan lewat ORM atas **seluruh model** yang punya field `many2one` ke `product.pricelist`, plus pemeriksaan langsung ke basis data:

| Sumber rujukan | Hasil |
|---|---|
| `pos.config.pricelist_id` | **2 baris** (id 6 & 7) → dirapikan lebih dulu ke id 3 |
| `pos.order.pricelist_id` | **0** (tidak ada order yang memakai pricelist arsip) |
| `product.pricelist.item.base_pricelist_id` | **0** (tidak ada pricelist lain yang berbasis pricelist ini) |
| `res.config.settings.pos_pricelist_id`, relasi pricelist di settings | **0** |
| `sale.order`, `pos.preset`, `product.label.layout`, `loyalty.program`, `res.country.group` | **0** |
| `ir_default`, tabel property | 0 (Odoo 19 tidak lagi menyimpan tabel property) |
| Rujukan wajib (`required`) yang menghalangi | tidak ada |

### 2.3 Keputusan yang diambil

* **`pos.config` 6 & 7 tidak dihapus**, hanya diarahkan ke `Harga Normal` — keduanya arsip, tidak punya order/sesi, tetapi dipertahankan sebagai jejak konfigurasi skenario "dine in". (`PLANNING` §8 butir 4 hanya meminta *arsip*, dan keduanya memang sudah arsip.)
* **Pricelist id 5 (`Harga Platform Online`) dipertahankan** meski 0 order memakainya, karena ia dipakai untuk perhitungan harga platform (`ceil500(×1,10)`) di laporan analisa.

### 2.4 Dampak

| Aspek | Dampak |
|---|---|
| Transaksi & jurnal | **tidak ada** — 32.700 order POS / omzet 2.384.428.500 dan 4.054 jurnal tidak berubah |
| Laporan keuangan & dashboard | **tidak ada** — HPP Agustus 449.863.602,21 dan persediaan 241.605.391,06 tetap sama |
| UI POS / master harga | hilang 1 pilihan pricelist yang **sudah tidak aktif**; kedua outlet aktif (id 1 & 2) sudah memakai `Harga Normal` sejak awal |
| Rollback | tersedia: `backups/rollback_pricelist_dinein_predelete_2026-09-15/` berisi CSV pra-hapus (`product_pricelist.csv`, `product_pricelist_item.csv`, `pos_config.csv`) |

---

## 3. Item 2 — Database sisa `tmp_cost_snap` dihapus

### 3.1 Keadaan sebelum dihapus

| Item | Nilai |
|---|---|
| Ukuran | **142 MB** (dibanding `Test1` 231 MB) |
| Terakhir diubah | 11 September 2026 13:47 (sisa fase analisa HPP) |
| Isi | 749 tabel · 887 jurnal · 4.515 order POS · memuat modul kustom `geprekyukss_dashboard` & `geprekyukss_pos` |
| Pemakai | **3 koneksi idle** dari server Odoo (tidak ada transaksi berjalan) |

### 3.2 Tindakan (aman dulu, baru hapus)

```bash
# 1) diarsipkan lebih dulu (jaring pengaman) -> 18 MB
pg_dump -Fc -h db -U odoo --no-owner --no-privileges tmp_cost_snap \
  > backup_snapshot_tmp_cost_snap_2026-09-15.dump

# 2) putuskan koneksi lalu hapus
psql -h db -U odoo -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='tmp_cost_snap';"
psql -h db -U odoo -d postgres -c 'DROP DATABASE "tmp_cost_snap";'
```

### 3.3 Hasil & dampak

| Sebelum | Sesudah |
|---|---|
| `Test1`, `postgres`, `template0`, `template1`, **`tmp_cost_snap`** | `Test1`, `postgres`, `template0`, `template1` |
| Ruang terpakai 142 MB | **0 MB** (bersih) |

* Ruang yang dibebaskan: **142 MB**; setelah dikurangi berkas arsip (18 MB) tetap hemat **≈124 MB**.
* Rollback: `createdb tmp_cost_snap && pg_restore --no-owner --role=odoo -d tmp_cost_snap backup_snapshot_tmp_cost_snap_2026-09-15.dump` (perlu saring `SET transaction_timeout` bila server PostgreSQL 15 — lihat catatan di `README_BACKUP.md`).
* Skrip analisa lama yang membaca `tmp_cost_snap` tidak lagi bisa dijalankan langsung; datanya sudah **tidak relevan** karena seluruh koreksi F1–F3 sudah masuk ke `Test1`.

---

## 4. Bukti verifikasi (setelah kedua perapian)

| Uji | Hasil |
|---|---|
| 59 metrik kunci (dibandingkan dengan baseline **pra-F7**) | 58 identik; **satu-satunya delta** `pricelist_items` **309 → 206** (−103, persis baris harga pricelist yang dihapus — memang diharapkan) |
| `test_f2_tb_crosscheck` | ✅ ALL PASS |
| `test_f5_pl_parity` | ✅ ALL PASS |
| `test_f5b_bs_parity` | ✅ ALL PASS |
| `test_f6_aged_partner` | ✅ ALL PASS |
| `test_report_actions` | ✅ ALL PASS |
| `test_beranda_overhaul` | ✅ SEMUA CHECK BERHASIL |
| Order POS / omzet / jurnal | 32.700 / 2.384.428.500 / 4.054 (tidak berubah) |
| Output skrip | `fails: tidak ada` · `RESULT: SELESAI` |

---

## 5. Jejak audit

| Item | Keterangan |
|---|---|
| Skrip | `scripts/perbaikan_15_kerapian_f7.py` — pemindaian rujukan otomatis + dry-run default (`RUN=1` untuk eksekusi) |
| Objek berubah | 1 `product.pricelist` (id 4) + 103 `product.pricelist.item` dihapus · 2 `pos.config` (id 6, 7) `pricelist_id` 4 → 3 · 1 database (`tmp_cost_snap`) dihapus |
| Objek **tidak** berubah | order POS, sesi, jurnal, akun, nominal, HPP, laba, persediaan, harga jual, BOM, partner |
| Berkas arsip baru | `backup_snapshot_tmp_cost_snap_2026-09-15.dump` (18 MB, diabaikan git) · `backups/rollback_pricelist_dinein_predelete_2026-09-15/` (CSV pra-hapus) |
| Backup utama | `backups/odoo_Test1_2026-09-15/` **diregenerasi setelah perapian ini** (dump 17 MB + zip 28 MB + CSV master) sehingga isi backup = keadaan sistem sekarang; baseline di dalamnya sudah `pricelist_items = 206` |
| Catatan teknis | `odoo shell` **tidak commit otomatis** — uji pertama sempat menunjukkan perubahan "hilang" karena di-rollback saat shell keluar; skrip kini memanggil `env.cr.commit()` di mode `RUN=1` (pola sama seperti `perbaikan_10..13`) |

### Cara mengulang

```bash
# dry-run (laporan saja)
su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
  --db_user odoo --db_password odoo --log-level=warn" < scripts/perbaikan_15_kerapian_f7.py

# eksekusi (idempotent: pricelist arsip sudah bersih → tidak melakukan apa-apa)
RUN=1 su odoo -s /bin/bash -c "RUN=1 odoo shell -d Test1 ..." < scripts/perbaikan_15_kerapian_f7.py
```

---

## 6. Sisa item F7 (belum dikerjakan — butuh keputusan/prioritas)

| # | Item | Catatan |
|---|---|---|
| 1 | Isi `date_range` + `account_fiscal_year` **atau** matikan bila laporan OCA tidak memakainya | modul OCA terpasang tapi 0 baris data |
| 2 | Putuskan `partner_statement` & `account_tax_balance` (dipakai / di-uninstall) | saat ini 0 transaksi |
| 3 | Isi `partner_id` untuk 1.898 baris AR POS (`11210011`) | umur piutang & statement per pelanggan belum bisa diatribusi |
| 4 | Hapus/permanenkan `pos.config` id 6 & 7 (Dine In) | kini arsip tanpa order; harga sudah diarahkan ke `Harga Normal` |
| 5 | Putuskan **24 menu POS** yang tidak pernah terjual dalam 72 hari | aktifkan promo atau nonaktifkan |
| 6 | Lengkapi panel UI placeholder (Rekap per Outlet/Hari, Transaksi 15/hal, Produk Terlaris, Kas & Bank, **Jadwal Penyusutan**, Stok Menipis) | sebagian menunggu F4 (register aset) & F5 (lokasi) |
| 7 | Impor rekening koran bank (BSI/e-wallet) bila fitur Rekonsiliasi Bank ingin nyata | sekarang hanya 146 baris rekening koran kas |
