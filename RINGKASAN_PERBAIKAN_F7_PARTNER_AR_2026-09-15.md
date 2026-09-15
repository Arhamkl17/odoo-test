# Ringkasan Perbaikan F7 — Partner pada 1.898 Baris AR POS

**Tanggal:** 15 September 2026 · **Sistem:** Odoo 19 (`Test1`) · **Skrip:** `scripts/perbaikan_16_partner_ar_pos.py` (dry-run default, `RUN=1` eksekusi, `RESET=1` membatalkan)
**Status:** ✅ **Selesai & terverifikasi** · **Angka keuangan:** **tidak ada yang berubah** (murni metadata partner)

---

## 1. Ringkasan singkat

Seluruh **1.898 baris** akun `11210011 Account Receivable (PoS)` sebelumnya **tanpa partner**, sehingga laporan per pelanggan (umur piutang & pernyataan partner) tidak bisa diatribusi. Kini semua baris sudah punya partner **per kanal pembayaran** (6 partner, keputusan pemilik):

| Kanal (metode bayar POS) | Partner | Baris | Debit | Kredit | Saldo |
|---|---|---:|---:|---:|---:|
| QRIS | **QRIS Acquirer** (baru, id 58) | 292 | 1.210.280.000,00 | 1.210.280.000,00 | 0,00 |
| Kartu · Mallengkeri Kartu | **Kartu Acquirer** (baru, id 59) | 438 | 526.508.500,00 | 526.508.500,00 | 0,00 |
| GoFood (OVO) | GoFood Platform (id 19, sudah ada) | 292 | 132.921.000,00 | 132.921.000,00 | 0,00 |
| Tunai · Mallengkeri Tunai | **Kasir Tunai** (baru, id 60) | 292 | 131.921.000,00 | 131.921.000,00 | 0,00 |
| GrabFood (GO-PAY) | GrabFood Platform (id 20, sudah ada) | 292 | 257.056.000,00 | 257.056.000,00 | 0,00 |
| ShopeeFood (ShopeePay) | ShopeeFood Platform (id 21, sudah ada) | 292 | 125.742.000,00 | 125.742.000,00 | 0,00 |
| **Total** |  | **1.898** | **2.384.428.500,00** | **2.384.428.500,00** | **0,00** |

Sisi **debit** (jurnal `POSS`, penutupan sesi kasir) dan sisi **kredit** (jurnal settlement `QRIW/BNK1/BNKB/OVOW/GPYW/SPPW/CSH2/CSHB`) diberi partner yang **sama**, sehingga saldo per partner tetap 0 — sesuai kenyataan bahwa tiap sesi dilunasi hari itu juga.

---

## 2. Aturan atribusi (yang disetujui pemilik)

1. **Per kanal pembayaran**, bukan per pelanggan: seluruh 32.700 order POS memang tidak punya partner (transaksi kasir tanpa identitas pembeli), sehingga yang bisa diatribusi adalah **pihak lawan kanal pembayaran**.
2. Platform memakai partner yang **sudah ada** (`GoFood/GrabFood/ShopeeFood Platform`) — sebelumnya partner ini menganggur (0 referensi).
3. Dibuat **3 partner baru** bergaya "acquirer/kas": `QRIS Acquirer`, `Kartu Acquirer`, `Kasir Tunai`.

### Cara kanal ditentukan (deterministik, bukan tebakan)

| Sisi | Sumber penentu | Contoh |
|---|---|---|
| Debit (jurnal `POSS`) | label baris `"/ - <metode>"` → dipetakan ke kanal | `"/ - QRIS"` → QRIS |
| Kredit (settlement) | kode jurnal → kanal (`QRIW` QRIS, `BNK1`/`BNKB` Kartu, `CSH2`/`CSHB` Tunai, `OVOW` GoFood, `GPYW` GrabFood, `SPPW` ShopeeFood) | `GPYW/2026/00001` → GrabFood |

### Verifikasi silang yang dijalankan sebelum menulis

* **949 pasangan rekonsiliasi** (`account.partial.reconcile`) dicocokkan: **0 pasangan beda kanal** → pemetaan debit & kredit konsisten 100%.
* `0` baris gagal dipetakan dari 1.898 baris.
* Baris yang sudah punya partner: 0 (tidak ada yang ditimpa).

---

## 3. Dampak yang terukur

### 3.1 Laporan pernyataan partner (OCA `partner_statement`) — **kini berisi**

| Partner | Baris pernyataan (1 Jun–31 Agu) | Debit | Kredit | Item terbuka |
|---|---:|---:|---:|---:|
| QRIS Acquirer | 292 | 1.210.280.000,00 | 1.210.280.000,00 | 0 |
| Kartu Acquirer | 365 | 526.508.500,00 | 526.508.500,00 | 0 |
| Kasir Tunai | 292 | 131.921.000,00 | 131.921.000,00 | 0 |
| GoFood Platform | 292 | 132.921.000,00 | 132.921.000,00 | 0 |
| GrabFood Platform | 292 | 257.056.000,00 | 257.056.000,00 | 0 |
| ShopeeFood Platform | 292 | 125.742.000,00 | 125.742.000,00 | 0 |
| *Rina Kartika (kontrol, tanpa transaksi)* | *0* | *0,00* | *0,00* | *0* |

Sebelum perbaikan, semua pernyataan itu kosong (mesin laporan memfilter per `partner_id`).

### 3.2 Laporan umur piutang (`aged partner`) — **tetap kosong, dan itu wajar**

Diuji sebelum & sesudah: **0 baris**. Sebabnya struktural, bukan kegagalan: laporan umur hanya menampilkan **piutang yang belum dilunasi**, sedangkan seluruh 1.898 baris AR POS sudah `reconciled` (sisa = 0) sejak perbaikan F2. Jadi:
* atribusi partner kini **siap** dan akan muncul sebagai sub-baris per partner begitu ada piutang terbuka (mis. sesi yang settlement-nya belum masuk);
* selama semua sesi dilunasi, laporan umur memang legit kosong — ini bukan efek perbaikan ini.

### 3.3 Angka keuangan & sistem — **tidak berubah**

| Uji | Hasil |
|---|---|
| 59 metrik kunci vs baseline pra-perbaikan | 57 identik; **2 delta yang diharapkan**: `partners` 49 → **52**, `partners_active` 46 → **49** (3 partner baru) |
| Order POS / omzet / jurnal / HPP Agu / persediaan | tidak berubah (32.700 · 2.384.428.500 · 4.054 · 449.863.602,21 · 241.605.391,06) |
| TB debit = kredit | tidak berubah (perubahan hanya metadata partner, bukan nominal) |
| 6 test parity proyek | **ALL PASS**, termasuk `test_f6_aged_partner` |
| Period lock | tetap `2026-08-31` (dibuka sementara saat menulis, lalu dipasang kembali) |

---

## 4. Jejak audit

| Item | Keterangan |
|---|---|
| Skrip | `scripts/perbaikan_16_partner_ar_pos.py` — pemetaan kanal + verifikasi silang rekonsiliasi + buka/tutup period lock otomatis + dry-run default |
| Objek berubah | 1.898 `account.move.line` (`partner_id` terisi) · 3 `res.partner` baru (id 58 QRIS Acquirer, 59 Kartu Acquirer, 60 Kasir Tunai) |
| Objek **tidak** berubah | nominal debit/kredit, akun, jurnal, tanggal, nomor entri, status rekonsiliasi, order POS, HPP, laba, persediaan, master produk/harga |
| Cara mengulang | dry-run: `su odoo -s /bin/bash -c "odoo shell -d Test1 ..." < scripts/perbaikan_16_partner_ar_pos.py` · eksekusi: tambah `RUN=1` (idempotent: baris yang sudah berpartner dilewati) |
| Cara membatalkan | `RUN=1 RESET=1 ... < scripts/perbaikan_16_partner_ar_pos.py` → `partner_id` dikosongkan lagi pada baris AR POS (partner baru tetap ada, bisa diarsipkan manual) |
| Catatan teknis | baris Jun–Agu terkunci `fiscalyear_lock_date`; skrip membuka lock → menulis → memasang kembali (pola `PLANNING` §13.5). `odoo shell` tidak commit otomatis → skrip memanggil `env.cr.commit()` |

---

## 5. Sisa item F7

| # | Item | Status |
|---|---|---|
| 3 | Isi `partner_id` pada 1.898 baris AR POS | ✅ **selesai 15 Sep** (dokumen ini) |
| 4 | Pricelist arsip & `pos.config` 6/7 | ✅ selesai (`RINGKASAN_PERBAIKAN_F7_KERAPIAN_2026-09-15.md`) |
| 6 | Hapus DB sisa `tmp_cost_snap` | ✅ selesai (dokumen yang sama) |
| 1 | Isi `date_range` + `account_fiscal_year` **atau** matikan | ⏳ terbuka |
| 2 | Putuskan `partner_statement` & `account_tax_balance` (pakai / uninstall) — *catatan: `partner_statement` kini terbukti berguna* | ⏳ terbuka |
| 5 | Putuskan 24 menu POS yang tidak pernah terjual | ⏳ terbuka |
| 7 | Lengkapi panel UI placeholder (Kas & Bank, Jadwal Penyusutan, Stok Menipis, dll.) | ⏳ terbuka (menunggu F4/F5) |
| 8 | Impor rekening koran bank untuk fitur Rekonsiliasi Bank | ⏳ terbuka |
