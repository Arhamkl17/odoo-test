# Inspeksi Sistem ERP — 15 Sep 2026

> **Lingkungan:** Odoo 19.0 (proses PID 1) · DB PostgreSQL 15.19 `Test1` (228 MB) · host `db`
> **Metode:** 100% read-only — `psql` (query langsung ke DB) + `odoo shell` (jalur ORM) + menjalankan test parity milik proyek. Tidak ada satu pun data yang diubah.
> **Cakupan:** 3.613 jurnal · 8.218 baris jurnal · 32.700 order POS · 70.353 baris order · 146 sesi · 2.252 stock move · 205 template produk · 100 BOM (940 baris) · 138 modul terpasang.

---

## 0. Verdict Ringkas

| # | Area | Verdict | Bukti utama |
|---|------|---------|-------------|
| A | Lingkungan & instalasi modul | ✅ **SEHAT** | Odoo hidup, 138 modul `installed`, 0 modul menggantung, semua OCA versi `19.0.x` |
| B | Engine akuntansi (double-entry, state, COA) | ✅ **BENAR** | 3.613 move semua `posted`, 0 tidak balance, DR = CR, tidak ada move tanpa baris |
| C | Parity laporan internal (TB / L-R / Neraca / MIS / dashboard) | ✅ **KONSISTEN** | 6 test parity proyek **ALL PASS** — MIS == dashboard == GL (toleransi 0,01) |
| D | Transaksi POS → pembayaran → settlement → bank | ✅ **REKONSILIASI PENUH** | 8 metode bayar == total order per bulan persis; AR PoS & Outstanding Receipts = 0 |
| E | Harga jual di transaksi vs master | ✅ **100% SESUAI** | 0 dari 70.353 baris yang menyimpang dari `Harga Normal` / `ceil500(×1,10)` |
| F | **Engine HPP (BOM → COGS)** | ❌ **UNDERSTATED Rp 14,91 jt (1,39%)** | NASI & ES TEH (sub-resep) tidak pernah dibebankan |
| G | **Persediaan: GL vs sub-ledger stok** | ⚠️ **SELISIH Rp 3,29 jt (1,35%)** | GL 244,90 jt vs `stock.quant.value` 241,61 jt |
| H | Jejak audit (nomor, gap, lock date) | ⚠️ **LEMAH** | 146 nomor POS tidak ikut tanggal akuntansi; 28 nomor hilang di 7 jurnal; tidak ada period lock (`sequence_number` NULL sendiri = desain modul OCA, bukan cacat — lihat §6) |
| I | Mesin alur Odoo (PO/picking/aset) | ⚠️ **DILEWATI** | 0 `stock.picking`, 0 PO, 0 aset di register OCA |
| J | Modul OCA: terpasang tapi menganggur | ⚠️ | `account_asset_management` (0 aset), `account_fiscal_year` & `date_range` (0 baris), `partner_statement` & `account_tax_balance` (0 transaksi) |
| K | **Laporan vs data nyata klien** | ❌ **TIDAK SAMA** | Omzet sistem 4,2× omzet nyata; HPP 44,5% vs 59,4% nyata; margin bersih 47,4% vs 19,3% nyata |

**Kesimpulan satu paragraf:** sistem ERP **berjalan dengan baik dan mesin akuntansinya benar** —
semua jurnal seimbang, buku besar ↔ laporan ↔ dashboard saling cocok sampai 0,01 rupiah, dan arus
POS → pembayaran → e-wallet → bank → trial balance tertutup penuh. Yang **tidak** benar ada tiga:
(1) HPP kurang catat Rp 14,9 jt karena dua sub-resep dilewati, (2) nilai persediaan di GL berbeda
Rp 3,3 jt dari sub-ledger stok, dan (3) **angkanya bukan angka nyata klien** — dataset ini adalah
portofolio sintetis 2 outlet (20 Jun–31 Agu 2026) yang omzetnya ±4× lipat data POS asli dan rasio
biayanya jauh lebih bagus daripada L/R Agustus asli klien.

---

## 1. Lingkungan & Instalasi

| Item | Nilai |
|---|---|
| Proses | `/usr/bin/odoo --db_host db` (PID 1) |
| DB | `Test1` 228 MB (ada sisa DB `tmp_cost_snap` 142 MB — kandidat dibersihkan) |
| Modul `installed` | **138** · `to upgrade`/`to install`/`to remove`: **0** |
| Addons lokal | 33 folder = 31 OCA + 2 kustom (`geprekyukss_dashboard`, `geprekyukss_pos`) |
| Versi OCA | semua `19.0.x` (mis. `mis_builder 19.0.1.2.0`, `account_financial_report 19.0.0.0.21`) — tidak ada modul versi lama/nyangkut |

---

## 2. Engine Akuntansi — ✅ BENAR

| Uji | Hasil |
|---|---|
| `account_move` | 3.613 — **semua `posted`**, 0 draft |
| Saldo per move (`Σdebit = Σcredit`) | **0 move tidak balance** |
| Total `Σdebit − Σcredit` seluruh DB | **0,00** |
| Move tanpa baris / baris tanpa akun / tanpa nama / tanpa tanggal | 0 / 0 / 0 / 0 |
| Nama move duplikat | 0 |
| Tanggal baris ≠ tanggal move | 0 |
| Akun terpakai | 44 dari 237 akun COA |
| Trial Balance Agustus 2026 | 45 akun, DR = CR = **4.655.647.075,68** |
| Neraca 31 Agu 2026 | Aset **2.096.616.034,24** = Kewajiban **0** + Ekuitas 964.900.000 + Laba YTD 1.131.716.034,24 ✅ seimbang |
| Laba Rugi Agustus (MIS) | Pendapatan 998.380.500 · Beban 525.332.494 · Laba 473.048.006 |

**Test parity proyek (dijalankan ulang hari ini, `odoo shell`):**

| Test | Hasil |
|---|---|
| `test_f5_pl_parity` (MIS L/R == dashboard == GL mentah) | **ALL PASS** |
| `test_f5b_bs_parity` (Neraca MIS == dashboard == GL; NI Neraca == Laba L/R) | **ALL PASS** |
| `test_f2_tb_crosscheck` (TB per akun == ORM; Neraca seimbang) | **ALL PASS** |
| `test_f6_aged_partner` (bucket umur == AML mentah) | **ALL PASS** |
| `test_report_actions` (9 laporan OCA: shape + export PDF/XLSX) | **ALL PASS** |
| `test_beranda_overhaul` (27 asersi payload Beranda) | **ALL PASS** |

---

## 3. Transaksi POS — ✅ REKONSILIASI PENUH

| Bulan | Order | Omzet POS | Pembayaran (`pos_payment`) | Akun pendapatan GL |
|---|---:|---:|---:|---:|
| Jun 2026 (20–30) | 5.298 | 383.505.500 | 383.505.500 | 383.505.500 |
| Jul 2026 | 13.713 | 1.002.542.500 | 1.002.542.500 | 1.002.542.500 |
| Agu 2026 | 13.689 | 998.380.500 | 998.380.500 | 998.380.500 |
| **Total** | **32.700** | **2.384.428.500** | **2.384.428.500** | **2.384.428.500** |

* Semua order `state = done`; 146 sesi **semua `closed`** (73 hari × 2 outlet).
* 8 metode bayar (Tunai, Kartu, QRIS, GoFood-OVO, GrabFood-GOPAY, ShopeeFood-ShopeePay, + Tunai/Kartu Mallengkeri) — totalnya **persis** sama dengan omzet tiap bulan.
* Harga di baris order: **56.460** baris = `Harga Normal`, **13.893** baris = `ceil500(normal × 1,10)` (platform) = **515.719.000** → **0 anomali**; komisi 15% = **77.357.850** terposting 😀 sesuai.
* Piutang POS (`11210011`) net 0, `Outstanding Receipts` net 0 → siklus settlement tertutup; saldo e-wallet/kas semua **positif** (tidak ada kas minus).
* 146 baris rekening koran **kas** (CSH2/CSHB) semua terekonsiliasi.

---

## 4. ❌ TEMUAN-1 — HPP kurang catat Rp 14.913.643 (1,39%)

**Cara uji:** HPP terposting (akun 5101.01/02/04) dibandingkan dengan rekomputasi independen
`Σ(qty terjual × resep BOM, ekspansi rekursif) = 1.075.021.852,90`.

| | Nilai |
|---|---:|
| HPP terposting (STJ) | 1.060.108.209,75 |
| HPP menurut resep (independen) | 1.075.021.852,90 |
| **Selisih** | **−14.913.643,15** |

**Akar masalah:** `PAKET AYAM SEGEPOK BEREMPAT` (terjual **954** pcs) komponennya adalah **menu lain**
(`NASI ×5`, `ES TEH ×5` → 4.770 masing-masing). Kedua produk itu bertipe `consu` dengan
`is_storable = false`, sehingga:

* generator HPP (`scripts/hpp_fifo_segmented_2toko_72hari_v2.py`) hanya meledakkan BOM **1 level** dan menyaring `is_storable` → NASI & ES TEH **tidak dibeli dan tidak dibebankan**;
* buktinya persis: `4.770 × (1.368,85 + 1.757,70) = 14.913.643,50` = selisih yang ditemukan.

**Dampak:** laba kotor & laba bersih **lebih tinggi Rp 14,9 jt** dari yang seharusnya (Agustus: 473,05 jt → 458,13 jt bila dikoreksi). Material anak NASI/ES TEH juga tidak pernah masuk pembelian/konsumsi.

---

## 5. ⚠️ TEMUAN-2 — Persediaan GL ≠ sub-ledger stok (Rp 3,29 jt / 1,35%)

| Sumber | Nilai |
|---|---:|
| Neraca (akun `11300180 Inventory` + residu `1103.01/02/03`) | **244.899.264,41** |
| Sub-ledger stok (`stock.quant.value`, 100 quant, 2 gudang) | **241.605.389,15** |
| Selisih | **3.293.875,26** |

* Penyebab utama: quant **NASI (1.432.471,55)** + **ES TEH (1.839.394,55)** = 3.271.866,10 — keduanya produk `consu` non-storable sehingga Odoo menilainya **0**, padahal ikut dinilai di saldo awal GL; sisanya residu pembulatan 22.010 pada `1103.xx`.
* Selain itu stok awal di-posting ke akun **berbeda** (`11300180`) dari akun alur pembelian/konsumsi (`1103.01/02/03`) — dua akun ini hanya "kebetulan" cocok karena **pembelian = konsumsi** (selisih Rp 734,53), sehingga saldo stok akhir = saldo awal.
* **Akibat nyata:** tab **Persediaan** dashboard menampilkan 241,61 jt (Pallangga 134,25 jt + Mallengkeri 107,36 jt) sementara tab **Neraca** menampilkan 244,90 jt — dua angka persediaan dalam satu aplikasi.

---

## 6. ⚠️ TEMUAN-3 — Jejak audit lemah

> **Koreksi 15 Sep 2026 (saat F3 dikerjakan).** Dua baris di tabel ini awalnya salah baca dan
> sudah dibetulkan di bawah: `sequence_number`/`sequence_prefix` **NULL itu memang desain
> modul OCA `account_move_name_sequence`** (hanya diisi untuk jurnal bermode terkunci-hash),
> dan lubang nomor bukan "1 per jurnal" melainkan **28 nomor** yang tersebar. Nomor entri
> audit (`entry_number`) ternyata **terisi** dan konsisten — jadi bukan "tidak terekam".

| Uji | Hasil |
|---|---|
| `sequence_number` / `sequence_prefix` | **NULL semua** (4.054 move) — ⚠️ **bukan cacat**: modul OCA `account_move_name_sequence` hanya mengisi kolom ini untuk jurnal `restrict_mode_hash_table` (di sini: 0 jurnal). Penomoran resmi memakai **`ir.sequence`** per jurnal, dan `_get_last_sequence()` modul itu sengaja dipanggil `with_prefix=None` sehingga kolom tsb tidak dipakai |
| Nomor hilang per jurnal | **28 nomor di 7 jurnal** (diukur ulang): `PBNK1/2026/` 295–297 · `BNKB/2026/` 74–76 · `GPYW · OVOW · QRIW · SPPW /2026/` masing-masing 147–149 · `MISC/2026/06/` 3, 21 · `MISC/2026/07/` 2, 20–22 · `MISC/2026/08/` 2, 20–22 |
| Jejak nomor audit umum (`entry_number`, OCA `account_journal_general_sequence`) | **terisi 4.054 baris**, unik, tanpa duplikat — tetapi juga berlubang **28 nomor** (`2026/00000001`–`2026/00004082`) → **persis sama** dengan 28 lubang nomor jurnal ⇒ jejaknya konsisten: 28 entri pernah dinomori lalu dihapus/dibatalkan |
| Prefiks jurnal POS | ke-146 move bernama `POSS/2026/**09**/xxxx` padahal bertanggal Jun–Agu (dibuat 14 Sep lalu tanggalnya di-backdate) |
| `create_date` semua move | **September 2026** (semua jurnal dibuat bersamaan, tanggal akuntansi ke belakang) |
| Period/tax/fiscal-year lock | **kosong semua** — entri terposting masih bisa diubah/dihapus (OCA `account_journal_lock_date` & `account_lock_date_update` terpasang tapi tidak dipakai) |

---

## 7. ⚠️ TEMUAN-4 — Mesin alur Odoo dilewati (data disuntik skrip)

| Objek | Jumlah | Konsekuensi |
|---|---:|---|
| `stock.move` | 2.252 (`done`, semua punya JE valuasi) | — |
| `stock.picking` | **0** (`picking_type_id` NULL semua) | Tidak ada dokumen penerimaan/pengiriman; laporan berbasis picking kosong |
| `purchase.order` | **0** | Tidak ada PO/AP; 1.060 jt pembelian bahan dikredit langsung ke **Bank BSI** (kas keluar) |
| `stock.scrap` | 0 | Panel "Waste/Susut" selalu nol |
| Aset di register OCA (`account_asset`) | **0** | Penyusutan diposting manual via JE (beban susut Agu 6.330.252,73); jadwal penyusutan tidak ada |
| Pajak | 18 pajak ada (berisi), **0 baris pajak terpakai**; `amount_tax` POS = 0 | Laporan PPN (OCA `vat_report`) & `account_tax_balance` kosong |
| Piutang tanpa partner | **1.898 baris** (akun `11210011`) | Laporan per pelanggan (`partner_statement`, aged partner) tidak bisa diatribusi (aman hanya karena saldonya 0) |
| Kewajiban | 32 akun `liability_current` + 6 `liability_payable` tersedia, **0 dipakai** | Neraca tidak punya hutang sama sekali |

Konsumsi bahan diposting ke lokasi `BTL/Food`, `BTL/Beverage`, `BTL/Pendukung` (usage = *production*)
**untuk kedua outlet** — konsumsi Pallangga pun masuk ke lokasi Mallengkeri. Nilai di lokasi produksi
menumpuk Rp 1.060.108.209 dan tidak pernah dikosongkan (secara akuntansi tidak salah karena bukan
lokasi internal, tapi atribusinya salah dan akan terus membengkak).

---

## 8. Master Data — ✅ bersih dengan 2 catatan

* 205 template aktif · 103 menu POS · 100 BOM/940 baris · 309 item pricelist · 46 partner · 22 jurnal (11 terpakai).
* Audit harga/BOM 13–14 Sep (harga platform, tahu/tempe, bubuk oranges, alas nasi, `standard_price` menu = HPP resep 100/100) **tidak ditemukan regresi**: 0 anomali harga di 70.353 baris transaksi.
* **Catatan 1:** **24 dari 103 menu POS belum pernah terjual** dalam 72 hari (dead SKU) — perlu keputusan master.
* **Catatan 2:** temuan lama yang masih terbuka: `consumption = 'warning'` di **100/100 BOM** (bukan flexible), `product.supplierinfo` tidak terhubung ke `standard_price` (tidak ada cron/harga sinkron), 0 route **Buy/Manufacture** pada produk, dan 1 nama kembar (`SAMBAL TOMAT MALINO` menu vs bahan).

---

## 9. Modul OCA — terpasang benar, sebagian menganggur

| Modul OCA | Status pemakaian |
|---|---|
| `mis_builder` (+`mis_builder_cash_flow`) | ✅ dipakai — 3 laporan (Laba Rugi, Neraca, Arus Kas), instance aktif, dipanggil dashboard & test parity |
| `account_financial_report` | ✅ dipakai — Trial Balance, Buku Besar, Journal Ledger, Umur Piutang, Open Items, PPN (PDF & XLSX via `report_xlsx`) |
| `account_move_name_sequence` | ✅ **dipakai** — inilah mesin penomoran resmi: `name` dihitung dari `ir.sequence` jurnal (`POSS/%(range_year)s/%(range_month)s/`, dst.). `sequence_number`/`sequence_prefix` memang dibiarkan NULL (hanya untuk jurnal terkunci-hash), dan wizard core `account.resequence.wizard` **tidak kompatibel** dengan modul ini |
| `account_journal_general_sequence` | ✅ **terisi** — `entry_number` 4.054 baris (nomor audit urut terpisah dari nomor jurnal) |
| `account_asset_management` | ⚠️ **menganggur** — 0 aset; penyusutan manual |
| `account_fiscal_year` / `date_range` | ⚠️ **0 baris data** — laporan OCA jalan dengan periode manual |
| `partner_statement` / `account_tax_balance` | ⚠️ menganggur (tidak ada partner di AR & tidak ada pajak) |
| Lock-date trio (`account_journal_lock_date`, `account_lock_date_update`, `account_journal_restrict_mode`) | ⚠️ terpasang, **tidak diaktifkan** |

---

## 10. ❌ TEMUAN-5 — Laporan TIDAK sama dengan data nyata klien

Fakta yang tersedia di repo: `Pesanan POS (pos.order) (8).xlsx` (ekspor POS asli **PALU TONDO**)
dan `laba_dan_rugi_agu_2026_geprek_yuksss!!!_palu_tondo (3).xlsx` (L/R asli Agustus 2026).

### 10.1 Volume & omzet (jendela 19 Jun – 31 Agu 2026)

| | Order | Omzet |
|---|---:|---:|
| Klien asli (Palu Tondo, 1 outlet) | 16.454 | **571.210.618** |
| Sistem `Test1` (Pallangga + Mallengkeri) | 32.700 | **2.384.428.500** |
| Selisih | 1,99× | **4,17×** |

Rata-rata per order: klien **34.716** vs sistem **72.918** (2,1×). Jumlah order per outlet per hari
justru mirip (klien Agustus 246/hari vs sistem 221/hari) → yang berbeda adalah **isi keranjang per
order**, bukan jumlah pembeli.

### 10.2 Laba rugi Agustus 2026

| Pos | Klien asli (Tondo) | Sistem (2 outlet) |
|---|---:|---:|
| Pendapatan bersih | 228.894.424 | 998.380.500 |
| HPP | 136.043.299 (**59,4%**) | 443.970.054 (**44,5%**) |
| Laba kotor | 92.851.125 (40,6%) | 554.410.446 (55,5%) |
| Beban operasi | 48.695.665 (21,3%) | 81.362.440 (8,1%) |
| **Laba bersih** | **44.155.460 (19,3%)** | **473.048.006 (47,4%)** |

Per outlet: sistem ±499 jt vs klien 229 jt (2,2×). Jadi meski master data beres, **laporan bulanan
yang keluar dari sistem ini bukan cerminan kinerja nyata klien** — margin bersih sistem 2,5× lebih
baik daripada realita.

### 10.3 Perbedaan struktur (bukan cuma angka)

| Aspek | Klien asli | Sistem |
|---|---|---|
| Diskon platform | kontra-pendapatan `4102.03/4102.04` (−6,93 jt GoFood, −24,59 jt GrabFood) | harga platform +10% (`ceil500`) + `Beban Komisi Platform` 15% (77,36 jt) |
| Pajak restoran (PB1) | beban, 686.461 | beban, ✓ sama perlakuannya |
| Hutang usaha / AP | ada (tidak terlihat di L/R) | **0 transaksi** |
| PPN/PPh | tidak ada di L/R | 0 (konsisten) |
| Persediaan | — | stok akhir = stok awal (pembelian = konsumsi), tidak ada penyesuaian akhir bulan |

Sesuai `PLANNING_PORTFOLIO_20JUNI_31AGUSTUS_2026-09-14.md`, data ini memang **portofolio sintetis**
(dibuat 14 Sep 2026 oleh rangkaian skrip, 2 outlet, harga master yang sudah dikoreksi) dan
`Trial Balance.pdf` lama sudah dinyatakan tidak dipakai. Untuk pemakaian sebagai **demo ke
recruiter/klien**, itu sah — asal tidak dipresentasikan sebagai “laporan nyata klien”.

---

## 11. Rekomendasi berurutan

| Prio | Aksi | Alasan |
|---|---|---|
| **P1** | Perbaiki HPP: ubah `NASI` & `ES TEH` jadi storable **atau** buat generator meledakkan BOM rekursif (2 level) | menutup HPP kurang catat Rp 14,91 jt + selisih persediaan Rp 3,29 jt sekaligus |
| **P1** | Satukan akun persediaan: pindahkan stok awal ke `1103.xx` + posting penyesuaian stok akhir bulanan | tab Persediaan dan Neraca harus menunjukkan angka yang sama |
| **P2** | Aktifkan period lock (`fiscalyear_lock_date` minimal 31 Agu 2026) + pastikan nama move lewat sequence asli (prefiks sesuai tanggal akuntansi) | jejak audit; nomor `POSS/2026/09/...` untuk entri Juni–Agustus menyesatkan — **selesai 15 Sep (F3)**: 146 nomor POS dinomori ulang per bulan + lock 31 Agu 2026 |
| **P2** | Daftarkan 7 aset ke `account_asset_management` | jadwal & beban penyusutan jadi otomatis, panel Aset punya sumber data |
| **P2** | Beri label “Data demo/portofolio sintetis 2 outlet (Jun–Agu 2026)” di dashboard + dokumennya | mencegah salah tafsir saat dibandingkan dengan L/R nyata klien (selisih 4×) |
| **P3** | Isi `date_range` & `account_fiscal_year`; rombak `partner_statement`/`account_tax_balance` atau matikan bila memang tak dipakai | modul terpasang tapi menganggur = beban perawatan tanpa manfaat |
| **P3** | Isi partner pada 1.898 baris AR POS; lengkapi panel yang masih placeholder (Transaksi Kas & Bank, Jadwal Penyusutan, Stok 15/hal, Produk Terlaris, Rekap per Outlet) | panel UI saat ini stok teks “menyusul F2–F7” |
| **P3** | Hapus DB sisa `tmp_cost_snap`, pricelist arsip `Harga Dine In` + config 6/7 arsip, dan putuskan 24 menu yang tidak pernah terjual | kerapian data |

---

## 12. Cara mengulang inspeksi ini

```bash
export PGPASSWORD=odoo
psql -h db -U odoo -d Test1 -P pager=off          # semua query di dokumen ini read-only

# test parity milik proyek
su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
  --db_user odoo --db_password odoo --log-level=warn" < scripts/test_f5_pl_parity.py
# ... test_f5b_bs_parity · test_f2_tb_crosscheck · test_f6_aged_partner · test_report_actions · test_beranda_overhaul
```
