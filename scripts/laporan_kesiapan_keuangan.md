# Laporan Kesiapan Keuangan — Odoo 19 Community, Database `Test1`

> **Tanggal pengecekan**: 25 Agustus 2026
> **Metode**: Investigasi read-only via XML-RPC (`search_read` / `search_count` / `read`)
> **Kredensial**: dari environment variable `ODOO_URL` / `ODOO_DB` / `ODOO_USER` / `ODOO_PASSWORD`
> **Server**: `http://localhost:8069` — Odoo 19.0-20260817, modul custom `geprekyukss_pos` v19.0.1.0.0
> **Tujuan**: memastikan sistem siap menerima data transaksi real untuk testing 1 bulan, khususnya sisi akuntansi/keuangan
>
> ⚠️ Tidak ada satupun data yang ditulis/diubah/dihapus selama pemeriksaan ini.

---

## Ringkasan Eksekutif

**Sistem BELUM SIAP** untuk mulai input transaksi 1 bulan. Ada:

- **2 blocker** yang harus diselesaikan dulu:
  1. Transaksi test sudah terlanjur masuk (3 order paid/done + 3 journal entry posted + sesi masih open)
  2. Stok minus tanpa opening balance (6 produk bahan baku qty negatif)
- **4 hal yang sebaiknya dibetulkan** sebelum mulai:
  1. Payment method non-tunai (QRIS/OVO/GOPAY/ShopeePay) belum dibuat padahal akun COA-nya sudah ada
  2. Journal kas masih menunjuk akun COA lama (`11110001 Cash`), bukan `1100.01`/`1100.02` dari COA baru
  3. Purchase journal default ke akun COGS (seharusnya akun pembelian/beban)
  4. Metode valuasi stok semua kategori masih default (standard/manual)

Estimasi kerja persiapan: **± setengah hari**, setelah itu sistem layak mulai periode testing bersih.

---

## Tabel Status Per Poin Pemeriksaan

| # | Poin | Status | Temuan Singkat |
|---|------|--------|----------------|
| 1a | Payment Method POS: Tunai | ✅ Siap | Journal `Restoran Kas` (CSH2) |
| 1b | Payment Method POS: Kartu | ✅/⚠️ | Journal `Bank` (BNK1), outstanding pakai akun chart lama `11120003` |
| 1c | Payment Method POS: Akun Pelanggan | ✅ Normal | Tanpa journal — wajar untuk tipe receivable |
| 1d | Payment Method QRIS/OVO/GOPAY/ShopeePay | ❌ Belum ada | Akun COA `1101.02–1101.05` sudah dibuat tapi belum jadi payment method |
| 2 | Journals (Sales/Purchase/Cash/Bank) | ⚠️ Perlu dirapikan | Semua ada & aktif, tapi default account masih acak ke COA lama/baru |
| 3 | Konfigurasi POS "Restoran" | ✅ Siap | 3 payment method terpasang, sales journal = `POS`, invoice journal = `Sales` |
| 4 | Metode valuasi stok (7 kategori custom) | ⚠️ Masih default | Semua `standard` cost + `periodic` valuation (manual) |
| 5 | Fiscal Year | ✅ OK | Tutup buku 31 Desember; model `account.fiscal.year` tidak ada lagi di Odoo 19 CE (normal) |
| 6 | Saldo awal (`account.move`) | ❌ Belum ada | 3 move existing = jejak closing sesi POS, bukan opening balance |
| 7 | Data transaksi existing (`pos.order`) | ❌ Bukan 0! | 7 order (3 paid/done total Rp104.895 + 4 cancel); sesi `00012` masih open |

Legenda: ✅ Siap · ⚠️ Perlu diisi/diperbaiki · ❌ Belum ada / blocker

---

## Detail Temuan Per Poin

### 1. Payment Methods POS (`pos.payment.method`)

| id | Nama | Aktif | is_cash | Journal Terhubung | Outstanding Account |
|----|------|-------|---------|-------------------|---------------------|
| 1 | Tunai | ✅ | ✅ | `[10] Restoran Kas` (CSH2) | — (wajar untuk cash) |
| 2 | Kartu | ✅ | ❌ | `[6] Bank` (BNK1) | `[117] Tanda Terima Belum Lunas` (`11120003`) |
| 3 | Akun Pelanggan | ✅ | ❌ | — (receivable) | — |

**Analisa:**
- `Tunai` → benar masuk ke journal kas resto. ✅
- `Kartu` → berfungsi, tapi outstanding account-nya `11120003 Tanda Terima Belum Lunas` berasal dari **chart lama**, sedangkan COA baru punya `1103.06 Outstanding Receipts`. Sebaiknya diseragamkan.
- `Akun Pelanggan` (Customer Account) memang tidak butuh journal. ✅
- **Yang hilang**: QRIS, OVO, GOPAY, ShopeePay. Padahal akun COA-nya sudah disiapkan:
  - `1101.01 Bank BSI` · `1101.02 QRIS` · `1101.03 OVO` · `1101.04 GOPAY` · `1101.05 SHOPEE PAY`

**Yang harus dilakukan:**
1. Buka `Point of Sale → Konfigurasi → Payment Methods → New`
2. Buat 4 payment method baru (QRIS / OVO / GOPAY / ShopeePay):
   - Tipe: bukan cash
   - Buat 1 journal baru bertipe **Bank** untuk masing-masing (atau satu journal bank per wallet), dengan *default account* menunjuk ke `1101.02` / `1101.03` / `1101.04` / `1101.05` — supaya saldo tiap wallet bisa dipisah saat rekonsiliasi
   - Jika ingin praktis: minimal ganti outstanding account `Kartu` ke `1103.06 Outstanding Receipts`
3. Masukkan payment method baru ke konfigurasi POS (lihat poin 3)

### 2. Journals (`account.journal`)

| id | Nama | Kode | Type | Default Account |
|----|------|------|------|-----------------|
| 1 | Sales | INV | sale | `[66] Sales` |
| 2 | Purchases | TAGIH | purchase | `[70] Cost of Goods Sold` ⚠️ |
| 6 | Bank | BNK1 | bank | `[3] Bank` (`11120001`) ⚠️ |
| 7 | Cash | CSH1 | cash | `[1] Cash` (`11110001`) ⚠️ |
| 10 | Restoran Kas | CSH2 | cash | `[1] Cash` (`11110001`) ⚠️ |
| 9 | POS | POSS | general (khusus sesi POS) | — |

**Analisa:**
- `Sales` → default ke akun penjualan, benar. ✅
- `Purchases` → default ke **COGS** kurang tepat; idealnya akun pembelian/beban langsung. ⚠️
- `Cash` dan `Restoran Kas` dua-duanya menunjuk ke akun `11110001 Cash` (chart lama). COA baru sudah menyediakan:
  - `1100.01 Kas Kasir`
  - `1100.02 Kas Operasional Resto`
  
  Artinya mutasi kas kasir vs kas operasional resto **tidak akan terpisah** di neraca. ⚠️
- `Bank` (BNK1) menunjuk ke `11120001` (chart lama), padahal COA baru punya `1101.01 Bank BSI`. ⚠️
- Adanya journal `POS` (general, tanpa default account) adalah **pola normal Odoo** untuk journal sesi POS. ✅

**Yang harus dilakukan:**
1. Buka `Akuntansi → Konfigurasi → Journals`
2. Edit `Restoran Kas` → Default Account = `1100.02 Kas Operasional Resto`
3. Edit `Cash` → Default Account = `1100.01 Kas Kasir` (atau nonaktifkan jika tak dipakai)
4. Edit `Bank` → Default Account = `1101.01 Bank BSI`
5. Edit `Purchases` → Default Account = akun pembelian (mis. `Pembelian` / beban sesuai COA)
6. Simpan. Tidak perlu restart server.

### 3. Konfigurasi POS (`pos.config`)

Konfigurasi **Restoran** (id=1, aktif):

| Field | Nilai | Status |
|-------|-------|--------|
| `payment_method_ids` | Kartu, Akun Pelanggan, Tunai (3 metode) | ✅ (tambah non-tunai baru nanti) |
| `journal_id` (sales journal sesi) | `[9] POS` (POSS) | ✅ pola standar Odoo |
| `invoice_journal_id` | `[1] Sales` (INV) | ✅ |

Bukti berjalan baik: JE closing sesi otomatis terbentuk (`POSS/2026/08/0001` → `CSH2/...`) dan baris receivable PoS mengarah ke akun khusus `Account Receivable (PoS)` (company default `account_default_pos_receivable_account_id` = `[5]`). ✅

**Yang harus dilakukan:** setelah payment method non-tunai dibuat (poin 1d), buka `Point of Sale → Konfigurasi → Settings → pilih "Restoran"` → bagian *Payments* → centang metode QRIS/OVO/GOPAY/ShopeePay.

### 4. Metode Valuasi Stok (`product.category`)

| id | Kategori | property_cost_method | property_valuation |
|----|----------|----------------------|--------------------|
| 1 | Goods | standard | periodic (manual) |
| 2 | Expenses | standard | periodic (manual) |
| 3 | Services | standard | periodic (manual) |
| 4 | Food | standard | periodic (manual) |
| 5 | Bahan Baku Beverage | standard | periodic (manual) |
| 6 | Bahan Baku Food | standard | periodic (manual) |
| 7 | Bahan Pendukung Menu | standard | periodic (manual) |
| 8 | Barang Perlengkapan Operasional | standard | periodic (manual) |
| 9 | Gas | standard | periodic (manual) |
| 10 | Menu Beverage | standard | periodic (manual) |
| 11 | Menu Food | standard | periodic (manual) |

**Analisa:** konsisten, tapi karena semuanya masih **nilai default bawaan** (bukan hasil keputusan konfigurasi), rencana FIFO/Average belum diterapkan. Untuk F&B:
- Bahan baku (Food/Beverage/Pendukung): umumnya **Average** atau FIFO
- Menu jadi & merchandise: Average cukup
- Barang habis pakai/gas: boleh manual/periodic (langsung beban)

Catatan penting: **ganti metode cost hanya aman jika kategori belum punya pergerakan stok bernilai** — lakukan SEBELUM input stok awal & transaksi.

**Yang harus dilakukan:** `Inventori → Konfigurasi → Kategori Produk` → edit kategori terkait → *Cost Method* = FIFO/Average, *Inventory Valuation* = Manual (periodic) atau Automated (real_time) sesuai kebutuhan laporan HPP.

Data pendukung: `product.template` = 202 item, 70 di antaranya sudah punya `standard_price > 0`, 86 bertipe storable.

### 5. Fiscal Year

- `res.company` (My Company, id=1): `fiscalyear_last_day = 31`, `fiscalyear_last_month = 12` → tutup buku tahunan tiap 31 Desember. ✅ (default wajar)
- Model `account.fiscal.year` **tidak tersedia lagi** di Odoo 19 Community (dicek via `ir.model`; hanya tersisa `account.fiscal.position*`). Tidak ada yang perlu dibuat. ✅

### 6. Saldo Awal / `account.move`

| name | journal | date | state | amount_total | ref |
|------|---------|------|-------|--------------|-----|
| POSS/2026/08/0001 | POS (POSS) | 2026-08-25 | posted | 64.380 | Restoran/00009 |
| CSH2/2026/00001 | Restoran Kas | 2026-08-25 | posted | 64.380 | — |
| CSH2/2026/00002 | Restoran Kas | 2026-08-25 | posted | 64.380 | — |

- **Tidak ada opening balance sama sekali.** Ketiga JE di atas adalah hasil otomatis *closing session* dari transaksi test POS tanggal 24–25 Agu 2026.
- Contoh struktur JE `POSS/2026/08/0001`: Kredit `VAT Sales` 6.380 + Kredit `Penjualan Menu Food` 58.000, Debit `Account Receivable (PoS)` 64.380 — pemetaan otomatis Odoo bekerja normal. ✅ (mekanismenya benar, datanya saja test)
- Akun `1103.09 Opening Inventory Balance` sudah disiapkan di COA tapi belum terpakai.

**Yang harus dilakukan (setelah bersih-bersih transaksi test):**
1. Input opening balance via `Akuntansi → Pembukuan → Entri Jurnal → New` bertanggal sebelum hari pertama testing, atau gunakan wizard *opening entries*
2. Input stok awal via `Inventori → Operasi → Physical Count` (akan membuat JE persediaan jika valuasi automated)

### 7. Data Transaksi Existing

| Model | Jumlah | Catatan |
|-------|--------|---------|
| `pos.order` | **7** | 3 paid/done + 4 cancelled (kosong) |
| `pos.payment` | 3 | Semua metode **Tunai** |
| `pos.session` | 12 | 11 closed, **1 open (`Restoran/00012`, mulai 25 Agu 08:59)** |

Detail order aktif:

| Order | State | Waktu | Total | Bayar |
|-------|-------|-------|-------|-------|
| Restoran - 000001 | paid | 25 Agu 09:03 | 40.515 | Tunai |
| Restoran - 000002 | done | 24 Agu 13:33 | 37.740 | Tunai |
| Restoran - 000003 | done | 24 Agu 13:34 | 26.640 | Tunai |
| 4 order lain (/) | cancel | — | 0 | — |

Total nilai test: **Rp104.895**.

**Fakta penting:** prompt awal menduga `pos.order = 0`, faktanya **sudah ada transaksi test yang masuk** (kemungkinan hasil uji coba sesi 23–25 Agu). Sesi `Restoran/00012` masih terbuka saat pengecekan.

---

## Rencana Tindak Lanjut (Urutan Eksekusi)

| Langkah | Aksi | Menu UI | Estimasi |
|---------|------|---------|----------|
| 0 | Backup DB dulu! `PGPASSWORD=odoo pg_dump -h db -U odoo Test1 > backup_$(date +%F).sql` | terminal | 5 mnt |
| 1 | Tutup sesi open `Restoran/00012`, hapus/batalkan 7 pos.order test | Point of Sale → Pesanan → Orders / Sessions | 15 mnt |
| 2 | Hapus 3 JE posted hasil closing test (POSS/2026/08/0001, CSH2/2026/00001-2) — reset dulu ke draft jika perlu | Akuntansi → Pembukuan → Entri Jurnal | 10 mnt |
| 3 | Rapikan default account journals (kas 1100.01/1100.02, bank 1101.01, purchase → akun belanja) | Akuntansi → Konfigurasi → Journals | 15 mnt |
| 4 | Buat payment method + journal bank untuk QRIS/OVO/GOPAY/ShopeePay (akun 1101.02–05), seragamkan outstanding `Kartu` ke 1103.06 | Point of Sale → Konfigurasi → Payment Methods | 30 mnt |
| 5 | Aktifkan metode baru di config POS "Restoran" | Point of Sale → Konfigurasi → Settings | 5 mnt |
| 6 | Set cost method kategori (Average/FIFO) — masih aman karena belum ada stok bernilai | Inventori → Konfigurasi → Kategori Produk | 15 mnt |
| 7 | Input opening balance JE + stok awal (physical count) | Akuntansi → Entri Jurnal · Inventori → Physical Count | 45 mnt |
| 8 | Smoke test: 1 transaksi POS tunai + 1 non-tunai → cek JE & laporan | POS + Akuntansi | 20 mnt |

Setelah langkah 0–8 tuntas, sistem **siap** menerima data transaksi real untuk testing 1 bulan.

---

## Lampiran: Catatan Teknis

- Endpoint XML-RPC: `http://localhost:8069/xmlrpc/2/common` (authenticate) & `xmlrpc/2/object` (execute_kw)
- Company aktif tunggal: `My Company` (id=1) — nama company belum diganti dari default, opsional dirapikan di `Pengaturan → Pengguna & Perusahaan → Perusahaan`
- COA di DB berisi campuran chart lama (kode `11110001` dst) dan chart baru Indonesia (kode `1100.x`, `1101.x`, dst) — inilah sumber ketidakkonsistenan pada default account journals
- Akun receivable PoS default perusahaan: `Account Receivable (PoS)` (id=5)
- Script pemeriksaan read-only tersimpan di `/tmp/opencode/cek_kesiapan_keuangan.py` (tidak dimasukkan ke repo; aman dijalankan ulang kapan pun)
