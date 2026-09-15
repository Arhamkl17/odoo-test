# Laporan Margin Menu & Jalan Menuju Profit — DB `Test1`

> Tanggal: 10 September 2026 · Metode: **read-only** via `odoo shell` (tidak ada data yang ditulis/diubah/dihapus — BoM, UoM, harga, jurnal tidak disentuh)
> Asumsi: komisi platform **15%** (sesuai koreksi Agustus 2026), target margin bersih **25%**
> Biaya menu dihitung dari `standard_price`; jika 0, dihitung dari **isi BoM** (BoM hanya dibaca)
> Saran harga memakai gaya penamaan **x777**, dibulatkan ke atas ribuan
> Script analisis: `cek_margin_profit.py` (untuk XML-RPC, butuh env ODOO_URL/DB/USER/PASSWORD)
> **Update 10 Sep 2026**: harga 15 menu rugi/margin-tipis sudah dinaikkan sesuai kolom "Saran" via `update_harga_x777.py` (hanya Sales Price; BoM, UoM, cost tidak disentuh). Harga lama di-backup di `backup_harga_sebelum_x777.json`.

---

## Ringkasan

| Kategori | Jumlah | Arti |
|---|---|---|
| **RUGI** (net margin < 0) | 9 menu nyata | Harga lebih murah dari biaya + komisi |
| **NAIK HARGA** (net margin < 15%) | 11 | Kontribusi terlalu tipis, rawan rugi |
| **PANTAU** (15–25%) | 5 | Di bawah target tapi masih sehat |
| **OK** (≥ 25%) | 105 | Sudah sesuai target |
| **COST 0** | 35 | Biaya tidak diketahui — 31 di antaranya **tidak punya BoM** |

⚠️ **Cara baca angka RUGI bahan baku**: produk seperti BERAS `harga 1 / cost 15` adalah **bahan baku yang salah masuk daftar `sale_ok`** (bisa dijual di POS dengan harga Rp1). Ini bukan menu rugi sungguhan — tapi harus dimatikan `sale_ok`-nya supaya tidak terjual salah harga di kasir.

---

## A. Menu Rugi Setelah Komisi 15% (prioritas tinggi)

> ✅ **SELESAI 10 Sep 2026**: semua harga pada kolom "Saran" di tabel A & B sudah diterapkan ke DB `Test1` (lihat `update_harga_x777.py`, backup di `backup_harga_sebelum_x777.json`, verifikasi 15/15 OK, tanpa pricelist penimpa). Harga lama tetap tercantum sebagai "Harga" di bawah.

| Menu | Harga | Cost | Net margin | Saran harga (net 25%) |
|---|---:|---:|---:|---:|
| MENU SAMBAL RICA MANADO | 3.000 | 2.667 | −4,6% | 4.777 |
| MOZZARELLA | 7.000 | 6.667 | −12,0% | 11.777 |
| AIR GELAS | 500 | 500 | −17,6% | 1.777 |
| MENU SAMBAL KOREK SURABAYA | 3.000 | 3.126 | −22,6% | 5.777 |
| MENU SAMBAL ORIGINAL | 3.000 | 3.126 | −22,6% | 5.777 |
| ES KRISTAL | 1 | 5 | −488% | (bahan baku, matikan sale_ok) |

**Menu sambal + MOZZARELLA = rugi riil tiap terjual.** Sembilan menu ber-flag RUGI lainnya adalah bahan baku ber-harga Rp1 (lihat catatan ⚠️ di atas).

## B. Margin Tipis < 15% — naikkan harga

| Menu | Harga | Cost | Net margin | Saran |
|---|---:|---:|---:|---:|
| KEMASAN VARIAN AYAM | 1.977 | 1.433 | 14,7% | 2.777 |
| PARUTAN KEJU | 5.000 | 3.667 | 13,7% | 6.777 |
| YUKSSS RAMA 1 | 15.000 | 11.021 | 13,6% | 18.777 |
| PKG LOKAL DUO | 32.777 | 24.464 | 12,2% | 40.777 |
| PAKET MEVVAH BERDUA | 30.777 | 22.997 | 12,1% | 38.777 |
| PAKET GEPREK BAKAR | 30.777 | 23.055 | 11,9% | 38.777 |
| SEGEPOK BERLIMA | 79.777 | 60.022 | 11,5% | 100.777 |
| PAKET YUKSSS MABAR | 28.000 | 21.679 | 8,9% | 36.777 |
| GEPREK ORIGINAL PAHA BAWAH | 10.000 | 8.279 | 2,6% | 14.777 |
| GEPREK ORIGINAL SAYAP | 10.000 | 8.279 | 2,6% | 14.777 |

Catatan: GEPREK ORIGINAL DADA/PAHA ATAS sudah 18,8% (kategori PANTAU). Sekali naik harga dari 12.000 → 14.777, ketiga varian GEPREK ORIGINAL konsisten.

## C. Menu Profitable (contoh terbaik, net margin tertinggi)

LEMON TEA 96,3% · ORANGE 88,9% · TELUR DADAR/CEPLOK 88,1% · PAKET BIG ORDER CRISPY MIX 83,3% · SAOS BBQ 76,1% · TELUR CRISPY 69,2% · NASI 65,5% · INDOMIE MEVVAH 61,6% · PAKET GEPREK LUMER 61,0%.

**Minuman dan paket Indomie adalah mesin profit — dorong penjualannya (bundling, upsell kasir).**

## D. Biaya Tidak Diketahui — 35 menu (net margin tidak bisa dihitung)

Tiga penyebab berbeda:

1. **31 menu TIDAK PUNYA BoM** — semuanya: varian GEPREK (ANDALAN/KEJU/MOZAA/SAMBAL TOMAT MALINO/SAOS BBQ/SAOS KEJU), semua PAKET GEPREK KEJU LUMER & SMOKEY BBQ (4), semua PKC (6), PKG (8), SAMBAL x4, TERONG CRISPY, BLACKCURRANT.
   → Ini menyebabkan: HPP POS terekonkonsiliasi tidak lengkap, margin menu ini tidak terpantau, dan stok bahan tidak terdekonciliasi otomatis saat menu terjual.
2. **SAOS KEJU** punya BoM tapi semua komponennya cost 0.
3. **Gift Card / Top-up eWallet / Uang Muka / Tips** — bukan menu, abaikan.

**Bahan baku cost=0 paling sering dipakai BoM menu yang sudah ada** (perlu diisi cost-nya dulu supaya BoM menangkap biaya nyata): lihat daftar di output analisis — pola umum: sambal, keju, bubuk minuman, kemasan kecil.

---

## Jalan Menuju Profit (urutan eksekusi, tanpa menyentuh BoM & UoM)

| # | Aksi | Cara | Estimasi |
|---|---|---|---|
| ~~1~~ | ✅ ~~Naikkan harga 6 menu RUGI + 10 menu tipis~~ — SELESAI 10 Sep 2026 (15/15 harga ter-update & terverifikasi) | ~~POS → Produk~~ script `update_harga_x777.py` | selesai |
| 2 | Matikan `sale_ok` bahan baku ber-harga Rp1 (±25 item: BERAS, GULA PASIR, MINYAK GORENG, dll.) | POS → Produk → uncheck "Can be Sold" | 15 mnt |
| 3 | Perbaiki harga menu RUGI terlebih dulu di harga platform (GoFood/GrabFood/ShopeeFood) supaya komisi 15% tidak menelan margin | dashboard masing-masing platform | 1 jam |
| 4 | Isi `standard_price` bahan baku cost=0 yang paling sering dipakai BoM | Inventori → Produk → edit Cost | 1 jam |
| 5 | Buat BoM untuk 31 menu tanpa BoM | Inventori → BoM *(langkah ini menyentuh BoM — minta konfirmasi user dulu)* | 3–4 jam |
| 6 | Push menu minuman & paket Indomie (margin 55–96%) lewat bundling/upsell | promosi + script kasir | berkelanjutan |
| 7 | Ulangi analisis bulanan: `python3 cek_margin_profit.py` (set env ODOO_*) | terminal | 5 mnt |

Langkah 1–3 sudah cukup menghilangkan semua rugi riil; langkah 4–5 membuat angka margin menu yang selama ini "gelap" jadi terukur.

---

## Lampiran: Dasar Perhitungan

- Net setelah komisi = `harga × 0,85`
- Net margin % = `(net − cost) / net`
- Harga saran = `cost / (0,85 − 0,25)` dibulatkan ke atas ke bilangan berpola x777 di ribuan berikutnya
- Sumber cost: `standard_price` produk; jika 0 dan ada BoM, jumlah `qty × standard_price` komponen
- Data diambil 10 Sep 2026 dari DB `Test1` (restore dari `Test1_2026-09-10_01-43-12.zip`), 204 produk sale_ok aktif, 70 BoM
