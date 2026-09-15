# Ringkasan Perbaikan Sistem — Nomor Jurnal, Kunci Periode & Nama Vendor (F3)

**Tanggal:** 15 September 2026 · **Sistem:** Odoo 19 (database `Test1`) · **Periode data:** 19 Juni – 31 Agustus 2026, 2 outlet (Pallangga & Mallengkeri)
**Status:** ✅ **Selesai & terverifikasi** · **Perubahan angka keuangan:** **tidak ada** (murni penomoran, kunci periode & data vendor)

---

## 1. Ringkasan singkat

Tiga hal dibereskan pada fase ini:

1. **Nomor jurnal kasir (POS)** sebelumnya memakai bulan pembuatan dokumen (**09**/2026 = September), padahal isi transaksinya bulan **Juni–Agustus**. Sekarang nomor sudah **mengikuti tanggal akuntansi**.
2. **Periode sudah dikunci** sampai **31 Agustus 2026** → entri lama tidak bisa diubah/dihapus lagi tanpa sengaja.
3. **Nama vendor/pemasok sudah terisi** (8 supplier) beserta harga belinya, sehingga pembelian bahan punya jejak pemasok, bukan lagi tanpa nama.

> **Angka laporan tidak berubah.** Total pendapatan, HPP, laba, dan nilai persediaan tetap sama persis dengan hasil perbaikan F1 + F2.

---

## 2. Nomor jurnal kasir: sebelum → sesudah

**Masalahnya:** seluruh 146 jurnal penutupan kasir dibuat pada 14 September 2026, sehingga Odoo memberi nomor bulan September (`POSS/2026/**09**/...`). Setelah tanggalnya dibetulkan ke Juni–Agustus, **nomornya tertinggal di bulan September** → menyesatkan saat diaudit/ditelusuri.

| | Sebelum | Sesudah |
|---|---|---|
| 22 jurnal | `POSS/2026/**09**/0001–0022` | **`POSS/2026/06/0001–0022`** (20–30 Juni) |
| 62 jurnal | `POSS/2026/**09**/0023–0084` | **`POSS/2026/07/0001–0062`** (1–31 Juli) |
| 62 jurnal | `POSS/2026/**09**/0085–0146` | **`POSS/2026/08/0001–0062`** (1–31 Agustus) |

**Penting untuk diketahui:** urutan nomor lama sudah benar (0001 = transaksi paling awal), yang salah hanya **penanda bulannya**. Jadi perubahan ini **1 banding 1** dan aturannya sederhana:

| Bulan | Nomor lama → nomor baru |
|---|---|
| Juni | `09/0001–0022` → `06/0001–0022` (nomor sama) |
| Juli | `09/0023–0084` → `07/0001–0062` (nomor lama − 22) |
| Agustus | `09/0085–0146` → `08/0001–0062` (nomor lama − 84) |

Isi jurnal (tanggal, akun, nominal, keterangan) **sama sekali tidak disentuh** — hanya label nomornya. Daftar lengkap 146 pasang nomor lama→baru tersedia bila diperlukan.

---

## 3. Apakah data demo 19 Juni – 31 Agustus aman? **Ya — terbukti utuh**

Kekhawatiran ini muncul karena saat menguji kunci periode, Odoo menampilkan perilaku “menggeser tanggal”. Yang terjadi sebenarnya:
**uji itu hanya transaksi percobaan** yang saya buat 1 baris di dalam transaksi uji, lalu **dibatalkan kembali** — tidak pernah tersimpan ke database (dibuktikan: 0 baris tersisa). Tujuannya hanya mengukur cara kerja kunci periode Odoo 19.

Bukti data demo tetap utuh:

| Yang diperiksa | Hasil |
|---|---|
| Rentang tanggal seluruh jurnal | **19 Juni 2026 – 31 Agustus 2026** |
| Jurnal bertanggal September atau setelahnya | **0** (tidak ada satu pun yang bergeser keluar) |
| Sisa transaksi uji / nomor sementara | **0** |
| Transaksi kasir (POS) | **32.700 order**, omzet **Rp 2.384.428.500** (sama seperti sebelumnya) |
| Sesi kasir tertutup & jurnalnya | **146 sesi / 146 jurnal** |
| Mutasi stok selesai (termasuk koreksi F1) | **2.692** |
| Total jurnal terposting | **4.054** |
| Debit = kredit per bulan (Jun / Jul / Agu) | **seimbang ketiganya** |
| HPP Agustus & nilai persediaan | **449.863.602,21** & **241.605.391,06** (sama dengan hasil F1+F2) |

**Jadi: kunci periode tidak mengubah riwayat.** Ia hanya membatasi penulisan *baru* ke dalam periode yang sudah dikunci.

---

## 4. Kunci periode (period lock) — apa artinya untuk kerja sehari-hari

| Hal | Penjelasan |
|---|---|
| Apa yang dikunci | `Global Lock Date = 31 Agustus 2026` → seluruh entri s/d 31 Agu 2026 |
| Efeknya | Entri lama **tidak bisa diubah/dihapus** lagi; dokumen Juni–Agustus praktis “final” |
| Kalau ada entri baru bertanggal dalam periode terkunci | Odoo 19 **tidak menolak**, tapi **memindahkan tanggalnya** ke hari pertama setelah kunci (September) — itulah “15-07 → 15-09” yang Anda lihat pada uji tadi |
| Risiko bila tidak diperhatikan | Koreksi yang niatnya masuk Juli/Agustus bisa **nyangkut di September** |
| Cara membuka sementara | Buka kunci → kerjakan koreksi → kunci lagi (perintahnya sudah disiapkan di `scripts/perbaikan_12_jejak_audit.py`) |
| Saran | Karena fase penyusutan aset & perapian berikutnya masih menyentuh Juni–Agustus, **buka kunci dulu** saat mengerjakannya, lalu tutup lagi setelah selesai |

**September kosong: tidak apa-apa dan memang begitu seharusnya** — dataset ini dipatok 19 Juni – 31 Agustus 2026. Penghitung nomor untuk September sudah direset ke `0001`, jadi begitu mulai mencatat September, nomornya rapi dari awal (mis. `POSS/2026/09/0001`, `MISC/2026/09/0001`) tanpa melanjutkan nomor lama.

---

## 5. Nomor jurnal yang hilang (28 nomor) — didokumentasikan, bukan disembunyikan

| Jurnal | Nomor hilang | Jumlah |
|---|---|---:|
| `PBNK1/2026/` (Bank) | 295, 296, 297 | 3 |
| `BNKB/2026/` (Bank Mallengkeri) | 74, 75, 76 | 3 |
| `GPYW/2026/` (Go-Pay) | 147, 148, 149 | 3 |
| `OVOW/2026/` (OVO) | 147, 148, 149 | 3 |
| `QRIW/2026/` (QRIS) | 147, 148, 149 | 3 |
| `SPPW/2026/` (ShopeePay) | 147, 148, 149 | 3 |
| `MISC/2026/06/` | 3, 21 | 2 |
| `MISC/2026/07/` | 2, 20, 21, 22 | 4 |
| `MISC/2026/08/` | 2, 20, 21, 22 | 4 |
| | **Total** | **28** |

**Penyebabnya sudah dipastikan:** saat pembuatan dataset, **28 entri sempat dinomori lalu dihapus/dibatalkan** — bukan salah penomoran. Buktinya, nomor audit umum sistem (`entry_number`, urut terpisah dari nomor jurnal) terisi 4.054 baris dan **berlubang tepat 28 nomor juga** (`2026/00000001`–`2026/00004082`). Dua penomoran independen menunjukkan lubang yang sama → jejaknya konsisten.

**Rekomendasi:** biarkan apa adanya dan laporkan sebagai *known gap* (praktik audit yang lazim: nomor yang sudah terbit tidak ditulis ulang). Bila Anda ingin urutan tanpa lubang, tersedia opsi `CLOSE_GAPS=1` — konsekuensinya nomor-nomor lama akan berubah dan harus disosialisasikan lebih dulu.

---

## 6. Daftar vendor (nama dummy bergaya supplier Makassar)

| Vendor | Domisili | Jumlah bahan | Contoh bahan yang dipasok |
|---|---|---:|---|
| **PT Sinar Niaga Abadi** | Jl. Boulevard No. 88, Makassar | 15 | Beras, bumbu bubuk, es kristal, keju, minyak, sambal & saos saset, tepung mix |
| **Toko Bahan Kue Andalan** | Jl. Sumbing No. 21, Makassar | 8 | Bubuk minuman (milo, oranges, blackcurrant, lemon tea), teh mix, air gelas/mineral, big cola |
| **UD Bumbu & Sambal Pasar Terong** | Pasar Terong, Wajo | 7 | Bumbu C, bumbu marinasi, garam, cuka, kecap, sambal tomat Malino, saos tiram |
| **PT Sumber Plastik** | Jl. Perintis Kemerdekaan KM 15, Daya | 6 | Plastik klip, plastik/kemasan segepok, kemasan geprek, mika bundar, gelas 22 oz |
| **CV Aneka Kemasan Utama** | Jl. Andi Pangerang No. 5, Makassar | 5 | Air galon, alas nasi, gelas 14 oz, pipet, thinwall sauce |
| **UD Berkah Tani** | Jl. Balla Lompoa No. 45, Makassar | 5 | Ayam cut 2 & cut 9, kulit ayam, nugget, telur |
| **CV Sumber Pangan Makassar** | Jl. Pajenekang No. 12, Makassar | 4 | Ayam cut 2 & cut 9, nugget, telur *(vendor alternatif)* |
| **UD Tahu Tempe Sehati** | Jl. Toddopuli Raya Timur, Panakukkang | 2 | Tahu, tempe |
| | | **52 baris** | **48 bahan** (4 bahan punya 2 vendor alternatif) |

Yang sudah dibenahi:

| Item | Hasil |
|---|---|
| Bahan yang tadinya **tanpa pemasok** | 21 bahan → **0** (semua bahan punya pemasok) |
| Harga pemasok vs biaya di sistem | **52 dari 52 baris sudah sama** (harga beli = biaya yang dipakai sistem, selisih ≤ Rp 0,01) |
| Lead time (estimasi kirim) | 1 hari untuk bahan segar (tahu, tempe, bumbu), 3 hari untuk kemasan & bubuk |
| Baris pemasok pada **produk menu** (bukan bahan) | **0** — dibersihkan, supaya tidak menyesatkan |
| Mutasi pembelian yang kini menyebut vendor | **2.344 dari 2.344** (100%) |
| Baris jurnal pembelian bahan yang bertanda vendor | **4.688 baris** |
| Perubahan nominal jurnal | **tidak ada** (hanya data pemasok) |

Manfaatnya: laporan pembelian per vendor dan harga terakhir per pemasok sekarang bisa dipakai untuk negosiasi, dan selisih harga beli vs biaya sistem bisa dilacak.

---

## 7. Jejak audit fase ini

| Item | Keterangan |
|---|---|
| Skrip penomoran & kunci periode | `scripts/perbaikan_12_jejak_audit.py` (mode uji dulu / `DRY-RUN`, eksekusi `RESEQUENCE=1 COUNTERS=1 LOCK=1`) |
| Skrip vendor | `scripts/perbaikan_13_vendor_supplier.py` (mode uji dulu / `RUN=1`) |
| Objek yang berubah | 146 nomor jurnal POS · 4 penghitung nomor (`ir.sequence`) · 1 tanggal kunci · 8 vendor · 52 harga pemasok · 2.344 mutasi · 4.688 baris jurnal |
| Yang **tidak** berubah | tanggal jurnal, akun, nominal, pendapatan, HPP, laba, persediaan, resep, harga jual |
| Backup pra-perbaikan | `backup_pre_perbaikan_inspeksi_2026-09-15.dump` |

**Hasil pengujian:** seluruh 6 test parity sistem **ALL PASS** — diuji **sebelum dan sesudah** kunci periode aktif; debit = kredit; neraca seimbang; 0 duplikasi nomor jurnal; 0 nomor jurnal yang tidak sesuai tanggal akuntansi.

---

## 8. Yang masih terbuka (butuh keputusan)

| # | Hal | Perlu keputusan |
|---|---|---|
| 1 | **Nomor hilang (28)** | Biarkan sebagai *known gap* (disarankan) atau rapatkan dengan `CLOSE_GAPS=1` |
| 2 | **Kunci periode saat fase berikutnya** | Buka dulu (`UNLOCK=1`) untuk pekerjaan register aset & perapian, lalu tutup lagi — atau tunda kunci sampai fase itu selesai |
| 3 | **Register aset tetap** | Penyusutan masih manual (akumulasi Rp 204,98 juta) → setujui pembuatan register di modul aset |
| 4 | **Data pemasok lanjutan** | Perlu isi NPWP/alamat resmi vendor, atau cukup nama & harga saja dulu |
| 5 | **Pelabelan data demo** | Tetapkan label “data demo/portofolio sintetis 2 outlet” agar tidak tertukar dengan laporan nyata klien |
