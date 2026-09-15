# PLANNING PERBAIKAN — Hasil Inspeksi Sistem ERP (15 Sep 2026)

> **Sumber temuan:** `INSPEKSI_SISTEM_2026-09-15.md` (inspeksi read-only: psql + odoo shell + 6 test parity proyek)
> **Lingkungan:** Odoo 19.0 · DB `Test1` · 32.700 order POS · 3.613 jurnal · 138 modul
> **Prinsip kerja (wajib):** (1) backup dulu, (2) skrip **dry-run default** — eksekusi hanya dengan `RUN=1`, (3) tiap fase ditutup dengan rekomputasi SQL + test parity, (4) master data yang sudah bersih **tidak disentuh**.
> **Status:** **F1 · F2 · F3 SELESAI** (lihat §12 & §13) — sisa: F4 (aset), F5 (picking/lokasi), F6 (label & recon), F7 (kerapian).
> ⚠️ Period lock 31 Agu 2026 **sudah aktif** → jalankan `UNLOCK=1` dulu sebelum koreksi periode berikutnya (§13.5).

---

## 0. Temuan → Fase Perbaikan

| Temuan (dari inspeksi) | Dampak | Fase |
|---|---|---|
| **T1** HPP kurang catat **Rp 14.913.643,50** (sub-resep NASI & ES TEH tidak dibebankan) | Laba Agustus lebih tinggi 5,89 jt; laba 72 hari lebih tinggi 14,91 jt | **F1** |
| **T2** Persediaan GL **244.899.265** vs sub-ledger stok **241.605.389** (selisih 3,29 jt) | Tab Persediaan ≠ tab Neraca | **F2** |
| **T3** Jejak audit lemah: 146 nomor POS berprefiks `POSS/2026/09` padahal bertanggal Jun–Agu, **28 nomor hilang** di 7 jurnal, tidak ada period lock (`sequence_number` NULL = desain OCA, bukan cacat) | Tidak siap audit; entri terposting masih bisa diubah | **F3** ✅ *selesai 15 Sep* |
| **T4** 7 aset (Rp 760 jt bruto) di luar register OCA `account_asset_management`; akum renovasi 4,07 jt tanpa aset bruto | Jadwal & beban penyusutan manual, tidak ada register | **F4** |
| **T5** 0 `stock.picking`, 0 PO, konsumsi Pallangga diposting ke lokasi produksi Mallengkeri | Laporan penerimaan/pengiriman kosong; atribusi outlet salah | **F5** |
| **T6** Laporan ≠ realita klien (omzet 4,17×, HPP 44,5% vs 59,4%, margin 47,4% vs 19,3%) tanpa label demo | Risiko salah tafsir saat dipresentasikan | **F6** |
| **T7** OCA menganggur (`date_range`, `account_fiscal_year`, `partner_statement`, `account_tax_balance`), panel UI placeholder, DB sisa `tmp_cost_snap`, 1.898 baris AR tanpa partner, 24 menu tak pernah terjual | Beban perawatan + laporan kosong | **F7** |

Temuan yang **tidak perlu diperbaiki** (sudah diverifikasi benar di inspeksi): double-entry/balance, parity MIS ↔ dashboard ↔ GL, rekonsiliasi POS → pembayaran → e-wallet → bank, harga jual di transaksi (0 anomali dari 70.353 baris), struktur BOM/UoM, dan 6 test parity proyek (ALL PASS).

---

## 1. Baseline Angka (pembanding sebelum/sesudah)

| Metrik | Nilai sekarang |
|---|---:|
| Omzet POS 72 hari | 2.384.428.500 |
| HPP terposting (5101.01 + .02 + .04) | 1.060.108.209,75 |
| HPP menurut resep (rekomputasi independen) | 1.075.021.852,90 |
| **Selisih HPP** | **−14.913.643,15** |
| Laba bersih Agustus (MIS) | 473.048.006,00 |
| Laba bersih YTD | 1.131.716.034,24 |
| Persediaan GL (`11300180` + `1103.01/02/03`) | 244.899.264,41 |
| Persediaan sub-ledger (`stock.quant.value`, 100 quant) | 241.605.389,15 |
| Aset tetap bruto / akumulasi | 760.000.000 / 204.981.598,13 |
| Beban penyusutan Jul & Agu | 6.330.252,73 / bulan |
| TB DR = CR | 4.655.647.075,68 (Agustus) |

**Backup wajib sebelum fase apa pun:**
```bash
pg_dump -Fc -h db -U odoo Test1 > backup_pre_perbaikan_inspeksi_2026-09-15.dump
```

---

## 2. F1 — Perbaiki Engine HPP Sub-Resep (P1) ⭐ prioritas tertinggi

### 2.1 Akar masalah
`PAKET AYAM SEGEPOK BEREMPAT` (terjual **150 Jun / 427 Jul / 377 Agu = 954 pcs**) memakai komponen **menu**, bukan bahan:

| Komponen | Per paket | HPP/unit | Bahan penyusunnya |
|---|---:|---:|---|
| `NASI` | ×5 | 1.368,85 | BERAS 1.135,26 · ALAS NASI 106,67 · CUKA 2,05 · GARAM 1,92 · MINYAK GORENG 12,13 · AIR GALON 110,83 |
| `ES TEH` | ×5 | 1.757,70 | TEH MIX 833,33 · ES KRISTAL 437,50 · AIR GALON 235,15 · GELAS 14 OZ 217,00 · PIPET 34,72 |

Ke-4.770 unit NASI + 4.770 unit ES TEH itu **tidak pernah dibeli & tidak pernah dibebankan** karena `NASI`/`ES TEH` bertipe `consu` dan `is_storable = false`, sementara `scripts/hpp_fifo_segmented_2toko_72hari_v2.py` hanya meledakkan BOM **1 level** lalu menyaring `is_storable`.

**Koreksi yang harus masuk** (954 paket × 15.632,75):

| Bulan | Nilai |
|---|---:|
| Jun (150) | 2.344.912,50 |
| Jul (427) | 6.675.184,25 |
| Agu (377) | 5.893.546,75 |
| **Total** | **14.913.643,50** |

Rincian per akun (≈, dihitung presisi dari BOM × `standard_price`):
`5101.02 HPP Food ±7,58 jt` · `5101.01 HPP Beverage ±3,97 jt` · `5101.04 HPP Pendukung ±3,36 jt`.

### 2.2 Keputusan yang perlu diambil (pilih satu)

| Opsi | Isi | Konsekuensi |
|---|---|---|
| **A (disarankan)** | Biarkan `NASI`/`ES TEH` non-storable (memang menu, bukan bahan), **perbaiki generator**: ledakkan BOM rekursif sampai bahan daun, dan bila komponen adalah menu ber-BOM, pakai komposisi 1 level di bawahnya | Master tidak berubah; HPP benar; berlaku juga untuk sub-resep lain di masa depan |
| **B** | Jadikan `NASI` & `ES TEH` storable (`is_storable = true`) | Perubahan master 2 produk + perlu quant/valuasi; risiko memengaruhi POS & pricelist |

### 2.3 Langkah eksekusi (Opsi A)

1. **Patch generator** — `scripts/hpp_fifo_segmented_2toko_72hari_v2.py` (atau salin jadi `..._v3.py`): fungsi explode rekursif dengan penjagaan siklus (`depth ≤ 5`), tanpa filter `is_storable` untuk komponen bahan; komponen menu ber-BOM diperlakukan sebagai sub-resep.
2. **Skrip koreksi historis (baru)** — `scripts/perbaikan_10_hpp_subresep.py`:
   * hitung kekurangan per outlet × per bulan dari BOM (bukan angka bulat),
   * buat **stock move konsumsi tambahan** `{WH,BTL}/Stok → lokasi produksi outlet yang benar` + JE valuasi (Dr `5101.0x` / Cr `1103.0x`) per segmen bulanan, mengikuti pola JE `STJ` yang sudah ada,
   * **dry-run default**; cetak tabel kuantitas & nilai sebelum/sesudah.
3. Jalankan `RUN=1`, lalu upgrade modul tidak diperlukan (tidak ada perubahan kode addon).

### 2.4 Verifikasi (gate fase)
```sql
-- HPP terposting harus == rekomputasi resep (toleransi 0,01)
with ... -- (query rekomputasi resep ada di INSPEKSI_SISTEM_2026-09-15.md §4)
```
* HPP total = **1.075.021.852,90**; TB tetap DR = CR; Neraca tetap seimbang.
* Laba Agustus turun dari 473.048.006,00 → **±467.154.459** (turunan 5.893.546,75).
* Jalankan ulang `test_f5_pl_parity`, `test_f5b_bs_parity`, `test_f2_tb_crosscheck`, `test_beranda_overhaul` → **ALL PASS**.

### 2.5 Risiko & rollback
Risiko rendah–sedang (menulis JE + stock move baru). Rollback: hapus JE & move bersuffix ref `KOREKSI-HPP-SUBRESEP` lalu restore backup. JE lama tidak diubah → jejak audit koreksi tetap terlihat.

---

## 3. F2 — Satukan Persediaan: GL == Sub-ledger Stok (P1)

### 3.1 Akar masalah
* Saldo awal di-posting ke akun `11300180 Inventory` (244.900.000), sedangkan seluruh alur pembelian/konsumsi memakai `1103.01/02/03` yang bersaldo ≈ 0 (kebetulan cocok karena **pembelian = konsumsi**; residu 734,53).
* Saldo awal menilai `NASI` & `ES TEH` sebesar **3.271.866,10**, padahal Odoo menilai produk non-storable = **0** → selisih 3,29 jt dengan sub-ledger.

| Komponen selisih | Nilai |
|---|---:|
| NASI (573,50 + 472,97 qty) | 1.432.471,55 |
| ES TEH (573,50 + 472,97 qty) | 1.839.394,55 |
| Residu pembulatan `1103.xx` | 22.010,22 |
| **Total** | **3.293.876,32** |

### 3.2 Langkah eksekusi
1. **Skrip baru** `scripts/perbaikan_11_persediaan_align.py` (dry-run default):
   * hitung `Σ stock.quant.value` (kanonik) vs `Σ saldo akun persediaan` per tanggal cut-off,
   * buat JE penyesuaian: Dr `31510010 Past Profit & Loss` → Cr akun persediaan (alokasi: `11300180` untuk porsi NASI/ES TEH, `1103.xx` untuk residu), ref `KOREKSI-PERSEDIAAN-AWAL`,
   * **putuskan satu akun persediaan**: usul — pindahkan saldo `11300180` ke `1103.02` (dan mapping `product.category` untuk Beverage/Pendukung), supaya alur baru & saldo awal satu akun,
   * tambahkan **JE penyesuaian stok akhir bulan** (opsional tapi disarankan) agar selisih bulanan selalu tertutup.
2. **Dashboard**: pastikan satu sumber angka untuk tab Persediaan **dan** Neraca — usul kanonik = `stock.quant.value` (fisik), Neraca mengikuti setelah JE di atas.

### 3.3 Verifikasi
* `Σ GL persediaan == Σ stock.quant.value` (selisih < Rp 1).
* `test_f2_tb_crosscheck` & `test_f5b_bs_parity` ALL PASS; Neraca tetap `Aset = Kewajiban + Ekuitas + Laba YTD`.
* Panel Persediaan (Pallangga 134,25 jt + Mallengkeri 107,36 jt = 241,61 jt) == baris Neraca.

---

## 4. F3 — Jejak Audit & Period Lock (P2) ✅ **SELESAI — rincian hasil di §13**

**Mesin penomoran (koreksi inspeksi):** penomoran TIDAK memakai `sequence.mixin` core melainkan modul OCA
`account_move_name_sequence` → `name` dihitung dari `ir.sequence` jurnal (`POSS/%(range_year)s/%(range_month)s/`).
Konsekuensinya: `sequence_number`/`sequence_prefix` sengaja NULL (hanya untuk jurnal terkunci-hash) dan
**wizard core `account.resequence.wizard` tidak kompatibel** (gagal di constraint `account_move_name_state_diagonal`
sebelum menulis apa pun) → penomoran ulang dilakukan dengan menulis `name` (dua tahap, agar tidak menabrak
`account_move_unique_name`) lalu menyelaraskan `ir.sequence.date_range.number_next`.

| Langkah | Hasil |
|---|---|
| 1. Lock | `fiscalyear_lock_date = **2026-08-31**` ✅ (field `period_lock_date` sudah tidak ada di Odoo 19; penggantinya `sale_lock_date`/`purchase_lock_date`) |
| 2. Nama & nomor | 146 entri POS dinomori ulang mengikuti tanggal akuntansi: `POSS/2026/06/0001–0022`, `/07/0001–0062`, `/08/0001–0062` (tidak ada lagi prefiks 09) ✅ |
| 3. Nomor hilang | **28 nomor** didokumentasikan sebagai *known gap* (nomor yang sudah terbit tidak ditulis ulang). Opsi rapatkan tersedia: `CLOSE_GAPS=1` |
| 4. Dokumentasi | daftar lubang + mapping penomoran lama→baru tercatat di §13 |
| 5. Bonus (diminta klien) | **nama vendor** untuk 48 bahan + tag vendor pada 2.344 stock move & 4.688 baris jurnal → §13.3 |

**Verifikasi (terpenuhi semua):** 0 entri yang namanya tidak sesuai tanggal; 0 duplikasi nomor; counter `ir.sequence`
selaras dengan nomor terakhir terpakai; TB DR = CR; HPP tidak berubah (449.863.602,21); 6 test parity **ALL PASS**
(diuji sebelum dan sesudah lock).

---

## 5. F4 — Aset Tetap Masuk Register OCA (P2)

**Data yang harus didaftarkan** `account_asset_management`:

| Aset | Perolehan (GL) | Akumulasi sekarang | Beban / bulan |
|---|---:|---:|---:|
| Peralatan Resto (`1105.03`) | 500.000.000 | 132.165.003,34 | 3.027.466,20 |
| Kendaraan (`1105.01`) | 150.000.000 | 37.500.000,00 | — (habis disusut) |
| Peralatan Kantor (`1105.02`) | 110.000.000 | 31.243.360,38 | 1.581.701,57 |
| Renovasi | **tidak ada akun bruto** ⚠️ | 4.073.234,41 | 1.721.084,96 |
| **Total** | 760.000.000 | 204.981.598,13 | **6.330.252,73** |

**Langkah:**
1. Tentukan profil aset (umur, metode garis lurus, akun beban & akumulasi) untuk 4 kelompok.
2. Buat record aset dengan **nilai buku berjalan** = gross − akumulasi sekarang (agar tidak dobel beban), tanggal mulai penyusutan = 1 Sep 2026.
3. Selesaikan data gap **Renovasi** (ada akumulasi, tidak ada aset bruto) — tentukan apakah nilai perolehan renovasi pernah masuk ke akun lain (`asset_current`/`expense`).
4. Mulai 1 Sep 2026, penyusutan **hanya** lewat modul (hentikan JE manual `MISC` penyusutan).

**Verifikasi:** total beban penyusutan modul Sep 2026 = **6.330.252,73**; register aset menampilkan 4 baris; panel "Jadwal Penyusutan" terisi; `test_f5b_bs_parity` tetap PASS.

---

## 6. F5 — Alur Odoo & Atribusi Outlet (P3)

| # | Aksi | Catatan |
|---|---|---|
| 1 | Ubah tujuan konsumsi Pallangga dari `BTL/Food` → lokasi produksi milik WH (buat `WH/Food`, `WH/Beverage`, `WH/Pendukung` bila belum ada) | memperbaiki atribusi outlet pada laporan persediaan/valuasi |
| 2 | Buat dokumen **receipt/delivery** (`stock.picking`) untuk 2.252 move historis **atau** dokumentasikan resmi bahwa ledger stok dihasilkan skrip | tanpanya: laporan penerimaan/pengiriman selamanya kosong |
| 3 | Opsional: buat PO/pembelian (sekarang 1.060 jt langsung kredit Bank BSI) agar ada siklus hutang–bayar | perlu keputusan apakah pembelian klien memang selalu tunai |
| 4 | Bersihkan nilai menumpuk di lokasi produksi (Rp 1.060.108.209) — mis. posting "inventory adjustment" ke produksi | kosmetik tapi mencegah kebingungan di laporan lokasi |

---

## 7. F6 — Realisme & Pelabelan Laporan (P2)

1. **Label jelas** di header dashboard + dokumen: *"Data demo/portofolio sintetis 2 outlet (20 Jun–31 Agu 2026) — bukan transaksi nyata klien"* (satu baris kecil di header + `README`).
2. **Skrip recon otomatis (baru)** `scripts/recon_vs_klien_asli.py`: membaca `Pesanan POS (pos.order) (8).xlsx` + `laba_dan_rugi_agu_2026...xlsx`, lalu mencetak tabel banding per bulan/outlet vs database (omzet, order, avg/order, HPP%, margin%).

   | Bulan | Klien (Tondo) | Sistem (2 outlet) | Rasio |
   |---|---:|---:|---:|
   | Jun (19–30) | 2.673 order / 92.555.081 | 5.298 / 383.505.500 | 4,14× |
   | Jul | 6.162 / 217.552.577 | 13.713 / 1.002.542.500 | 4,61× |
   | Agu | 7.619 / 261.102.960 | 13.689 / 998.380.500 | 3,82× |
   | **Total** | **16.454 / 571.210.618** | **32.700 / 2.384.428.500** | **4,17×** |
3. **Keputusan strategis** (butuh jawaban pemilik): tetap portofolio sintetis **atau** regenerasi agar proporsional dengan klien (kurangi isi keranjang ±2,1× / skala per outlet) **atau** impor order asli Tondo sebagai basis.
4. Pertimbangkan akun kontra-pendapatan `4102.03/4102.04` (diskon GoFood/GrabFood) seperti klien, sebagai alternatif "harga +10% & komisi 15%".

---

## 8. F7 — Kerapian OCA, Data & UI (P3)

| # | Aksi |
|---|---|
| 1 | Isi `date_range` + `account_fiscal_year`, atau matikan bila laporan OCA tak memakainya |
| 2 | Putuskan `partner_statement` & `account_tax_balance` (dipakai / di-uninstall) |
| 3 | Isi `partner_id` untuk **1.898 baris** AR POS (`11210011`) → aged partner & partner statement punya isi |
| 4 | Arsipkan pricelist `Harga Dine In` (id 4) + `pos.config` 6/7 arsip |
| 5 | Putuskan **24 menu POS** yang tidak pernah terjual dalam 72 hari (aktifkan promo / nonaktifkan) |
| 6 | Hapus DB sisa `tmp_cost_snap` (142 MB) |
| 7 | Lengkapi panel UI placeholder: Rekap per Outlet/Hari (F2), Daftar Transaksi 15/hal + Produk Terlaris berfoto (F3), Transaksi Kas & Bank + Rekonsiliasi (F5), Jadwal Penyusutan (F6), Stok 15/hal + Stok Menipis (F7) |
| 8 | Impor rekening koran bank (BSI/wallet) bila fitur Rekonsiliasi Bank ingin nyata (sekarang hanya kas 146 baris) |

---

## 9. Urutan Eksekusi & Estimasi

| Fase | Scope | Skrip utama | Estimasi |
|---|---|---|---|
| **F0** | Backup + catat baseline | `pg_dump` | 0,2 j |
| **F1** | HPP sub-resep | patch generator + `perbaikan_10_hpp_subresep.py` | 1 j |
| **F2** | Persediaan align | `perbaikan_11_persediaan_align.py` | 1 j |
| **F3** | Lock date + nomor | `perbaikan_12_jejak_audit.py` + `perbaikan_13_vendor_supplier.py` | ✅ selesai |
| **F4** | Register aset OCA | buat record aset + hentikan JE manual | 1 j |
| **F5** | Lokasi & picking | `perbaikan_14_lokasi_produksi.py` (nomor 12 & 13 sudah dipakai F3) | 1–1,5 j |
| **F6** | Label + recon vs klien | `recon_vs_klien_asli.py` + header dashboard | 1 j |
| **F7** | Kerapian OCA/data/UI | wizard + skrip kecil | 1,5–2 j |

**Total ≈ 8–9 jam** (F1 & F2 wajib berurutan sebelum F3/F4; F5–F7 bisa paralel).

---

## 10. QA Gate (berlaku tiap fase)

* [ ] Backup terbaru ada (`backup_pre_*_2026-09-15.dump`).
* [ ] Uji balance: `Σdebit − Σcredit = 0`; 0 move tidak balance.
* [ ] Neraca seimbang: Aset = Kewajiban + Ekuitas + Laba YTD.
* [ ] `test_f5_pl_parity` · `test_f5b_bs_parity` · `test_f2_tb_crosscheck` · `test_f6_aged_partner` · `test_report_actions` · `test_beranda_overhaul` → **ALL PASS**.
* [ ] Angka terdampak dicatat sebelum/sesudah (HPP, laba, persediaan, penyusutan).
* [ ] Tidak ada master (harga, BOM, UoM, pricelist) yang berubah tanpa keputusan eksplisit.
* [ ] Perubahan tercatat: skrip, ref JE, tanggal, dan alasan (jejak audit).

---

## 11. Di Luar Scope Planning Ini

* Regenerasi ulang dataset 72 hari dari nol (butuh keputusan F6 dulu).
* Import data transaksi klien yang sesungguhnya (Palu Tondo) sebagai produksi.
* Rekonsiliasi bank otomatis penuh (butuh berkas rekening koran dari klien).
* Perpajakan (PPN/PPh) — saat ini 0 transaksi pajak; bila klien PKP, perlu fase tersendiri.

---

## 12. STATUS PELAKSANAAN — F1 & F2 **SELESAI** (15 Sep 2026)

### 12.1 Artefak

| Item | Nilai |
|---|---|
| Backup sebelum perubahan | `backup_pre_perbaikan_inspeksi_2026-09-15.dump` (22 MB) |
| Generator dipatch | `scripts/hpp_fifo_segmented_2toko_72hari_v2.py` — explode BOM **rekursif** (`explode_need`, `MAX_DEPTH=8`, anti-siklus) |
| Skrip koreksi F1 | `scripts/perbaikan_10_hpp_subresep.py` (dry-run default, `RUN=1` eksekusi) |
| Skrip koreksi F2 | `scripts/perbaikan_11_persediaan_align.py` (dry-run default, idempotent) |
| Move baru F1 | **440** stock move (pembelian segmented + konsumsi), ref `KOREKSI-HPP-SUBRESEP ...` |
| JE koreksi F2 | **MISC/2026/06/0025** tanggal 2026-06-19, ref `KOREKSI-PERSEDIAAN-AWAL` |

### 12.2 Angka sebelum → sesudah

| Metrik | Sebelum | Sesudah | Selisih |
|---|---:|---:|---:|
| HPP total (72 hari) | 1.060.108.209,75 | **1.075.021.855,71** | +14.913.645,96 |
| HPP Juni | 170.394.673,27 | 172.739.586,15 | +2.344.912,88 |
| HPP Juli | 445.743.481,99 | 452.418.667,35 | +6.675.185,36 |
| HPP Agustus | 443.970.054,49 | 449.863.602,21 | +5.893.547,72 |
| Laba bersih Agustus | 473.048.006,00 | **467.154.458,28** | −5.893.547,72 |
| Laba bersih YTD | 1.131.716.034,24 | **1.116.802.388,28** | −14.913.645,96 |
| Margin bersih Agustus | 47,38% | **46,79%** | −0,59 pp |
| Persediaan GL (`asset_current`) | 244.899.267,57 | **241.605.391,06** | −3.293.876,51 |
| Persediaan sub-ledger stok | 241.605.391,06 | 241.605.391,06 | (basis) |
| Total aset (Neraca) | 2.096.616.034,24 | **2.078.408.511,77** | −18.207.522,47 |
| Ekuitas | 964.900.000,00 | **961.606.123,49** | −3.293.876,51 |
| Bank BSI | 1.238.967.130,87 | 1.224.053.482,81 | −14.913.648,06 (pembelian bahan) |
| `11300180 Inventory` | 244.900.000,00 | **0,00** (dipindah ke `1103.01/02/03`) | −244.900.000 |

> Selisih 2,81 rupiah vs angka acuan dokumen (1.075.021.852,90 vs 1.075.021.855,71) murni
> presisi desimal `standard_price` (0,0000003%) — dua metode (SQL rekomputasi dan ORM) saling menguatkan.

### 12.3 Bukti verifikasi

* **Persediaan tab == Neraca**: dashboard Persediaan **241.605.391,06** (Pallangga 134.248.970,18 + Mallengkeri 107.356.420,88) == GL `asset_current` **241.605.391,06** == `Σ stock.quant.value` **241.605.391,06**; cocok juga **per akun/kategori** (1103.01, 1103.02, 1103.03, 1103.05, 1103.10, 11300180).
* **Neraca seimbang**: aset 2.078.408.511,77 = kewajiban 0 + ekuitas+laba 2.078.408.511,77 (selisih 0,00).
* **TB seimbang**: debit = credit (MIS `Selisih (harus 0)` = 0,00); 0 jurnal tidak balance; 0 draft.
* **Semua 440 move baru F1 punya JE valuasi** (`stock_move.account_move_id` tidak null).
* **6 test parity proyek ALL PASS**: `test_f2_tb_crosscheck`, `test_f5_pl_parity`, `test_f5b_bs_parity`, `test_f6_aged_partner`, `test_report_actions`, `test_beranda_overhaul`.
* Satu angka HPP di seluruh sistem: dashboard Beranda & tab Biaya-HPP = MIS Builder = GL = **449.863.602,21** (Agustus).

### 12.4 Catatan pasca-perbaikan

* Koreksi F2 di-offset ke `31510010 Past Profit & Loss` (koreksi saldo awal), **bukan** beban periode → laba rugi tidak terpengaruh (PSAK: koreksi periode lalu → laba ditahan).
* Pembedahan HPP F1 memakai pola identik generator lama (pembelian segmented fresh 3 hari / dry 7 hari + konsumsi akhir bulan) sehingga sifat data tidak berubah: **pembelian = konsumsi, stok akhir = stok awal**.
* Temuan yang **masih terbuka** dari inspeksi: **F4** (register aset OCA), **F5** (picking/atribusi lokasi konsumsi), **F6** (label demo + recon vs klien), **F7** (kerapian OCA/UI). ~~F3~~ sudah selesai (§13).

---

## 13. STATUS PELAKSANAAN — F3 **SELESAI** (15 Sep 2026)

### 13.1 Artefak

| Item | Nilai |
|---|---|
| Skrip penomoran + lock | `scripts/perbaikan_12_jejak_audit.py` (dry-run default; `RESEQUENCE=1 COUNTERS=1 LOCK=1`) |
| Skrip vendor | `scripts/perbaikan_13_vendor_supplier.py` (`RUN=1`; `CLEAN_MENU=1` membersihkan supplierinfo produk menu) |
| Backup sebelum fase | `backup_pre_perbaikan_inspeksi_2026-09-15.dump` (dipakai sejak F1) |
| Ringkasan untuk klien | `RINGKASAN_PERBAIKAN_F3_2026-09-15.md` |

**Bukti periode demo utuh (19 Jun – 31 Agu 2026):** 4.054 jurnal terposting semuanya bertanggal dalam rentang itu,
**0 jurnal** bertanggal ≥ 1 Sep 2026, 0 sisa transaksi uji/label sementara (`F3TMP`), debit = kredit di tiap bulan,
32.700 order POS / omzet 2.384.428.500 & 146 sesi kasir tidak berubah, HPP Agustus 449.863.602,21 dan
persediaan 241.605.391,06 tetap sama dengan hasil F1+F2.

> Peta nomor lama→baru (diambil dari backup pra-F3, bukan dari memori): urutan nomor lama sudah kronologis,
hanya penanda bulannya salah → pemetaan 1:1: Juni n→n, Juli (n+22)→n, Agustus (n+84)→n.

### 13.2 Nomor jurnal: sebelum → sesudah

| Objek | Sebelum | Sesudah |
|---|---|---|
| Nama 146 entri jurnal POS | `POSS/2026/**09**/0001–0146` (dibuat di bulan Sep, di-backdate) | `POSS/2026/**06**/0001–0022`, `/07/0001–0062`, `/08/0001–0062` |
| Entri yang namanya tidak sesuai tanggal akuntansi | 146 | **0** |
| Duplikasi nomor dalam jurnal | 0 | **0** |
| `ir.sequence` POS (`ir.sequence.date_range`) | hanya range Agu (next 1) & Sep (next 147) | Jun (next 23) · Jul (next 63) · Agu (next 63) · Sep (next 1) |
| Counter 10 jurnal lain | sudah selaras (max+1) | tetap selaras (diverifikasi idempotent) |
| Lock date | kosong | `fiscalyear_lock_date = 2026-08-31` |

**Nomor hilang yang didokumentasikan (28 nomor — tidak dirapatkan):**

| Jurnal | Nomor hilang | Jumlah |
|---|---|---:|
| `PBNK1/2026/` | 295, 296, 297 | 3 |
| `BNKB/2026/` | 74, 75, 76 | 3 |
| `GPYW/2026/` | 147, 148, 149 | 3 |
| `OVOW/2026/` | 147, 148, 149 | 3 |
| `QRIW/2026/` | 147, 148, 149 | 3 |
| `SPPW/2026/` | 147, 148, 149 | 3 |
| `MISC/2026/06/` | 3, 21 | 2 |
| `MISC/2026/07/` | 2, 20, 21, 22 | 4 |
| `MISC/2026/08/` | 2, 20, 21, 22 | 4 |
| | **Total** | **28** |

> **Jejak silang yang meyakinkan:** penomoran audit umum OCA (`entry_number`, `account_journal_general_sequence`)
> terisi 4.054 baris dan berlubang **juga tepat 28 nomor** (`2026/00000001`–`2026/00004082`) → kesimpulan:
> 28 entri pernah diberi nomor lalu **dihapus/dibatalkan** saat pembuatan dataset, bukan salah penomoran.
> Karena itu lubangnya didokumentasikan (bukan dirapatkan): nomor yang sudah terbit tidak ditulis ulang.
> Bila klien mau urutan rapat tanpa lubang: `CLOSE_GAPS=1` (nomor lama berubah — harus disosialisasikan).

### 13.3 Vendor & supplierinfo (permintaan klien)

| Objek | Hasil |
|---|---|
| Vendor supplier | 8 vendor (4 lama dilengkapi + nama dummy gaya Makassar): **PT Sumber Plastik** (plastik/kemasan), **UD Tahu Tempe Sehati** (tahu-tempe), **UD Bumbu & Sambal Pasar Terong** (bumbu/saus), **PT Sinar Niaga Abadi**, **Toko Bahan Kue Andalan**, **CV Aneka Kemasan Utama**, **UD Berkah Tani**, **CV Sumber Pangan Makassar** |
| `product.supplierinfo` | **52 baris untuk 48 bahan** yang benar-benar dibeli (4 bahan punya 2 vendor alternatif: AYAM CUT 2, AYAM CUT 9, NUGGET AYAM, TELUR → CV Sumber Pangan Makassar + UD Berkah Tani). Sebelumnya 21 bahan tanpa supplier; harga kini = `standard_price` (52/52 baris), `delay` 1 hari untuk bahan fresh, 3 hari untuk kemasan/bubuk |
| Baris supplierinfo pada produk **menu** (menyesatkan) | **0** (dibersihkan, sebelumnya ada) |
| Tag vendor pada mutasi | **2.344/2.344** stock move pembelian (`partner_id` terisi penuh) |
| Tag vendor pada jurnal | **4.688** baris jurnal (Dr bahan 1.075.021.123 ≈ HPP 1.075.021.856) |
| Nominal jurnal | **tidak berubah** (murni metadata) |

### 13.4 Bukti verifikasi

* `total nama tidak sesuai tanggal: 0` · `duplikasi nomor dalam jurnal: 0` · counter selaras.
* TB debit = credit (diff 0,00) · Neraca tetap 2.078.408.511,77 = 0 + 961.606.123,49 + 1.116.802.388,28.
* HPP Agustus tetap **449.863.602,21** (F3 tidak mengubah nominal apa pun).
* 6 test parity **ALL PASS**, diuji **dua kali**: sebelum lock dan sesudah `fiscalyear_lock_date = 2026-08-31`.
* Uji perilaku lock (Odoo 19 = *postpone*, bukan error): entri uji bertanggal 2026-07-15 otomatis
  digeser ke **2026-09-15** dan bernomor `MISC/2026/09/0001` (dibatalkan lagi setelah uji).

### 13.5 ⚠️ Wajib dibaca sebelum fase berikutnya

Karena lock sudah aktif, koreksi periode Jun–Agu (F4 register aset, F5 lokasi, F7 pembersihan)
**akan digeser tanggalnya** oleh Odoo. Urutan kerjanya:

```bash
# 1) buka lock
UNLOCK=1 su odoo -s /bin/bash -c "odoo shell -d Test1 ..." < scripts/perbaikan_12_jejak_audit.py
# 2) kerjakan F4/F5/F7 ...
# 3) tutup lagi
LOCK=1  su odoo -s /bin/bash -c "odoo shell -d Test1 ..." < scripts/perbaikan_12_jejak_audit.py
```

Alternatif yang lebih tenang: **tunda lock** sampai F4–F7 selesai (skrip lock bisa dijalankan kapan saja).
