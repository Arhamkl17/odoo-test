# Ringkasan Perbaikan Sistem — HPP & Persediaan (F1 + F2)

**Tanggal:** 15 September 2026 · **Sistem:** Odoo 19 (database `Test1`) · **Ruang lingkup:** 20 Juni – 31 Agustus 2026, 2 outlet (Pallangga & Mallengkeri)
**Status:** ✅ **Selesai & terverifikasi** · **Perubahan master data (harga, resep, produk):** tidak ada — hanya koreksi angka transaksi

---

## 1. Ringkasan singkat

Hasil inspeksi sistem menemukan **dua kesalahan pencatatan**, keduanya sudah diperbaiki dan diuji:

1. **Biaya bahan untuk Nasi & Es Teh pada paket "Ayam Segepok Berempat" tidak pernah dicatat sebagai biaya** → HPP (harga pokok) kurang Rp 14,91 juta selama 3 bulan, sehingga laba tampak lebih tinggi.
2. **Nilai persediaan di Neraca berbeda Rp 3,29 juta** dengan catatan stok fisik (sub-ledger) → angka persediaan di laporan bisa berbeda tergantung layar yang dibuka.

Setelah perbaikan: **angka persediaan di seluruh laporan seragam (Rp 241.605.391,06)**, HPP sudah memuat seluruh bahan yang benar-benar terpakai, dan seluruh laporan (laba rugi, neraca, trial balance, dashboard, 9 laporan OCA) tetap **saling cocok sampai 0,01 rupiah**.

---

## 2. Temuan & perbaikan #1 — HPP kurang catat Rp 14,91 juta

**Masalahnya:** menu *Paket Ayam Segepok Berempat* resinya memakai **Nasi (5 porsi)** dan **Es Teh (5 gelas)** per paket. Karena Nasi & Es Teh adalah *menu jadi* (bukan bahan mentah), sistem lama melewatinya sehingga **bahan di baliknya** (beras, teh mix, es kristal, air galon, gelas, pipet, alas nasi, cuka, garam, minyak) tidak pernah dibeli maupun dibebankan sebagai biaya.

**Skalanya:** 954 paket terjual (150 Juni · 427 Juli · 377 Agustus) × 15.632,75 biaya bahan per paket.

**Rincian HPP per jenis (seluruh periode):**

| Komponen HPP | Sebelum | Sesudah | Selisih |
|---|---:|---:|---:|
| HPP Food (5101.02) | 955.745.239,56 | 963.324.090,69 | +7.578.851,13 |
| HPP Beverage (5101.01) | 55.122.966,44 | 59.097.944,98 | +3.974.978,54 |
| HPP Bahan Pendukung (5101.04) | 49.240.003,75 | 52.599.820,04 | +3.359.816,29 |
| **Total HPP** | **1.060.108.209,75** | **1.075.021.855,71** | **+14.913.645,96** |

**Cara perbaikan:** sistem dibuat meledakkan resep **bertingkat sampai bahan mentah** (bukan berhenti di menu jadi), lalu bahan untuk 954 paket tersebut **dibeli (Juni–Agustus) dan dikonsumsi** persis seperti pola pembelian outlet sehari-hari.

> Dampak yang perlu diketahui: kas bank berkurang **Rp 14.913.648,06** karena bahan tersebut memang harus dibeli. Sifat data tidak berubah — total pembelian tetap sama dengan total konsumsi, jadi saldo stok akhir tetap seperti semula.

---

## 3. Temuan & perbaikan #2 — Persediaan Neraca ≠ catatan stok

**Masalahnya:** saldo awal persediaan (19 Juni) tercatat Rp 244.900.000 di satu akun (`11300180 Inventory`), sedangkan seluruh mutasi pembelian/pemakaian memakai akun kategori (`1103.01/02/03`). Selisih Rp 3,29 juta muncul karena saldo awal itu **ikut menilai Nasi & Es Teh** (dua item menu yang oleh Odoo dinilai Rp 0) ditambah pembulatan.

**Hasil perbaikan:**

| | Sebelum | Sesudah |
|---|---:|---:|
| Nilai persediaan di Neraca (GL) | 244.899.267,57 | **241.605.391,06** |
| Nilai persediaan menurut catatan stok (sub-ledger) | 241.605.391,06 | 241.605.391,06 |
| Selisih | 3.293.876,51 ❌ | **0,00** ✅ |

Sekarang **tab Persediaan, Neraca, Trial Balance, dan dashboard menampilkan angka yang sama** — dan tidak hanya totalnya, tetapi juga **per kelompok barang**: Beverage Rp 13.671.692,76 · Food Rp 216.742.394,81 · Pendukung Rp 11.191.303,49 (+ per gudang: Pallangga Rp 134.248.970,18 / Mallengkeri Rp 107.356.420,88).

**Perlakuan akuntansinya benar:** selisih Rp 3.293.876,51 dibebankan ke **Laba Ditahan (Past Profit & Loss)**, **bukan** sebagai beban bulan ini — karena ini koreksi saldo awal, bukan biaya operasional baru. **Laba rugi tidak terpengaruh oleh koreksi ini.**

---

## 4. Dampak ke laporan

| Pos laporan | Sebelum | Sesudah | Keterangan |
|---|---:|---:|---|
| HPP Agustus 2026 | 443.970.054,49 | **449.863.602,21** | +5,89 jt (biaya yang tadinya terlewat) |
| Laba bersih Agustus 2026 | 473.048.006,00 | **467.154.458,28** | −5,89 jt |
| Margin bersih Agustus | 47,38% | **46,79%** | −0,59 poin |
| Laba bersih YTD (Jun–Agu) | 1.131.716.034,24 | **1.116.802.388,28** | −14,91 jt |
| Total Aset | 2.096.616.034,24 | **2.078.408.511,77** | −18,21 jt (14,91 jt bahan + 3,29 jt koreksi awal) |
| Total Ekuitas | 964.900.000,00 | **961.606.123,49** | −3,29 jt (koreksi saldo awal) |
| Saldo Bank BSI | 1.238.967.130,87 | **1.224.053.482,81** | −14,91 jt (pembelian bahan) |

Neraca tetap seimbang: **Aset 2.078.408.511,77 = Kewajiban 0 + Ekuitas & Laba 2.078.408.511,77** (selisih Rp 0,00).
Pendapatan/penjualan, stok fisik, resep, harga jual, dan pricelist **tidak berubah sama sekali**.

---

## 5. Jejak audit — skrip & nomor jurnal

**Skrip yang dijalankan** (semua `dry-run` default; eksekusi hanya dengan `RUN=1`):

| # | File | Fungsi |
|---|---|---|
| 1 | `scripts/hpp_fifo_segmented_2toko_72hari_v2.py` | generator HPP — dipatch agar meledakkan resep **rekursif** (perbaikan permanen untuk ke depan) |
| 2 | `scripts/perbaikan_10_hpp_subresep.py` | koreksi HPP sub-resep (pembelian segmented + konsumsi) |
| 3 | `scripts/perbaikan_11_persediaan_align.py` | penyelarasan nilai persediaan GL dengan sub-ledger stok (idempotent, bisa dipakai bulanan) |

**Nomor jurnal koreksi:**

| Ref | Nomor JE | Tanggal | Isi |
|---|---|---|---|
| `KOREKSI-HPP-SUBRESEP …` | **STJ/2026/2253 – STJ/2026/2692** (440 jurnal) | 20 Jun – 31 Agu 2026 | pembelian bahan + pemakaian untuk 954 paket (Dr HPP / Cr Persediaan) |
| `KOREKSI-PERSEDIAAN-AWAL` | **MISC/2026/06/0025** | 19 Jun 2026 | Dr 1103.01 13.671.693,81 · Dr 1103.02 216.743.126,21 · Dr 1103.03 11.191.303,47 · Cr 11300180 244.900.000,00 · Dr 31510010 3.293.876,51 |

**Backup sebelum perubahan:** `backup_pre_perbaikan_inspeksi_2026-09-15.dump` (22 MB) — dapat dipakai untuk mengembalikan kondisi sebelum perbaikan bila diperlukan.

**Hasil pengujian (semua harus lulus):**

| Uji | Status |
|---|---|
| Trial Balance: debit = kredit | ✅ 0,00 |
| Neraca: Aset = Kewajiban + Ekuitas + Laba | ✅ 0,00 |
| Jurnal tidak balance / masih draft | ✅ 0 / 0 |
| 440 stock move baru punya jurnal valuasi | ✅ 440/440 |
| 6 test parity sistem (F2, F5, F5b, F6, laporan OCA, Beranda) | ✅ **ALL PASS** |
| Satu angka HPP di semua layar | ✅ 449.863.602,21 (Agustus) |

---

## 6. Yang masih terbuka (butuh keputusan)

| # | Hal | Perlu keputusan |
|---|---|---|
| 1 | **Kunci periode** — belum ada *period lock*; entri lama masih bisa diubah | Tetapkan tanggal kunci (usul: 31 Agustus 2026) |
| 2 | **Register aset tetap** — penyusutan masih dihitung manual (belum lewat modul OCA), akumulasi Rp 204,98 juta | Setujui pembuatan register aset agar jadwal penyusutan otomatis |
| 3 | **Dokumen stok** — data mutasi stok historis dibuat tanpa dokumen penerimaan/pengiriman | Perlu dibuatkan dokumen atau dinyatakan cukup |
| 4 | **Pelabelan data** — dataset ini adalah **portofolio sintetis 2 outlet** (bukan transaksi asli klien); omzetnya ±4,2× data POS asli Palu Tondo | Tetapkan label "demo/portofolio" atau arah regenerasi |
| 5 | **Rekonsiliasi bank** — baru kas yang terisi, rekening koran bank belum diimpor | Sediakan berkas rekening koran bila fitur ini ingin aktif |
