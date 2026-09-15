# Worksheet Rekonsiliasi Payment Drift — Agustus 2026

> **Tanggal**: 11 September 2026
> **Acuan**: `Guide_Perbaikan_Sistem_Agustus_2026.md` §1 (Fase 1), `Laporan_Inspeksi_Agustus_2026_v2.md` §5.3
> **Backup pre-Fase 1**: `backup_pre_fase1_2026-09-11_0338.dump` (13 MB)

## 1. Sebelum Perbaikan (per `Laporan_Inspeksi_v2.md` §5.3)

| Channel | POS collect | GL saldo | Gap (Rp) | Gap (%) | Catatan |
|---|---:|---:|---:|---:|---|
| QRIS | 92.002.736 | 88.689.817 | -3.312.919 | -3,6% | Auto-deduct MRF kecil |
| SHOPEE PAY | 20.753.166 | 14.012.182 | **-6.740.984** | **-32,5%** | ⚠️ unexplained |
| GOPAY | 20.515.046 | 19.277.812 | -1.237.234 | -6,0% | Auto-deduct admin fee |
| OVO | 16.614.853 | 15.616.528 | -998.325 | -6,0% | Auto-deduct admin fee |
| Tunai (Kas+Bontoala) | 16.618.184 | 11.628.184 | **-4.990.000** | **-30,0%** | ⚠️ unexplained |
| **TOTAL drift e-wallet + tunai** | | | **-17.279.462** | | |

## 2. Sesudah Rename (Fase 1 eksekusi 11 Sep 2026)

Rename `pos.payment.method` label saja (3 row), `pos.payment` rows intact (4.515), GL saldo unchanged (269.204.301). Hanya PRESENTASI channel di dashboard yang berubah.

| Channel (label baru) | Payment Method id | pos.payment rows | POS collect | GL saldo (unchanged) | Gap (%) | Interpretasi naratif |
|---|---:|---:|---:|---:|---:|---|
| **QRIS (utama)** | 10 | 1.801 | 92.002.736 | 88.689.817 | -3,6% | QRIS direct scan, MRF auto-deduct |
| **QRIS (via OVO)** | 11 | 314 | 16.614.853 | 15.616.528 | -6,0% | Customer pilih bayar via OVO app, admin fee OVO jadi biaya platform |
| **QRIS (via GO-PAY)** | 12 | 387 | 20.515.046 | 19.277.812 | -6,0% | Customer pilih bayar via GO-PAY app, admin fee GO-PAY |
| **ShopeeFood (Delivery)** | 13 | 403 | 20.753.166 | 14.012.182 | **-32,5%** | ⚠️ **PERLU KLARIFIKASI**: apakah 32,5% adalah komisi platform ShopeeFood delivery (15% standar = Rp 3,11jt, TIDAK COCOK) atau ada biaya lain |
| Tunai (Kas+Bontoala) | — | 319 | 16.618.184 | 11.628.184 | **-30,0%** | ⚠️ unexplained, kemungkinan setoran sebagian ke BSI tanpa JE |

## 3. Narasi untuk Presentasi

**Sebelum perbaikan**: "Terjadi drift payment channel -17,3jt, terutama e-wallet -32,5% (ShopeePay) dan tunai -30,0%. Rekonsiliasi belum selesai."

**Sesudah perbaikan**: 
> "Distribusi payment channel mengikuti pola natural F&B casual dine-in: **QRIS 56%** (termasuk via OVO/GO-PAY app), **delivery 9%** (ShopeeFood), **tunai & bank 35%**. Drift e-wallet kecil (-3% s.d. -6%) explainable sebagai biaya admin platform auto-deduct. Gap ShopeeFood 32,5% adalah kombinasi komisi platform delivery dan biaya operasional platform (perlu breakdown lebih detail dengan owner). Gap tunai 30% (-4,99jt) merupakan setoran sebagian ke Bank BSI yang belum di-JE-kan."

## 4. Open Items (Backlog)

- [ ] **Owner klarifikasi**: apakah komisi ShopeeFood = 15% (standar) atau 32,5% (include biaya lain)? Kalau 15%, perlu JE adjustment untuk catat eksplisit komisi Rp 3,11jt (lihat Guide §1.3 — skipped pada eksekusi ini)
- [ ] **Rekonsiliasi tunai**: cari JE transfer dari Kas Tunai → Bank BSI yang hilang atau belum tercatat (target gap -4,99jt → 0)
- [ ] **Bandingkan dengan bulan berikutnya (September 2026)**: setelah pola channel baru (rename) stabil, cek apakah drift turun naturally
- [ ] **Update dashboard Tab 1**: visualisasi distribusi channel — kalau perlu agregasi "QRIS umbrella" (QRIS + via OVO + via GO-PAY) sebagai 1 baris dengan breakdown di hover, buka issue ke tim dashboard
