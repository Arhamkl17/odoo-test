# Planning — Adaptasi UI FinanceFlow PRO ke Dashboard Keuangan (12 Sep 2026)

> Dokumen kerja untuk AI agent (Buffy/Codebuff). Modal: 4 screenshot UI "FinanceFlow PRO"
> (template personal finance) + 7 foto dashboard existing "Dashboard Keuangan — Contra Group"
> (produksi, `addons/geprekyukss_dashboard/`).
>
> **Status roadmap utama**: `ROADMAP_DASHBOARD_KEUANGAN_2026-09-12.md` — F0 selesai, F1–F8 terkunci
> (lihat §G Keputusan Final). Dokumen ini **TIDAK mengubah urutan F0–F8**, melainkan
> menyisipkan 3 pekerjaan restyle sebagai **Wave paralel (sebut: F-UI)** yang boleh dikerjakan
> kapan saja karena murni kosmetik — tidak menyentuh compute OCA maupun struktur data.

---

## 0. Keputusan Final (hasil diskusi 12 Sep 2026)

| # | Topik | Keputusan |
|---|---|---|
| D1 | UI diadopsi dari FinanceFlow | Card-style Posisi Kas & Bank, Sidebar grouping (section header), Gauge score Status Keuangan |
| D2 | Riwayat Transaksi (tabel GL/TB gaya FinanceFlow) | **TIDAK dikerjakan di wave ini** — tetap ikut urutan roadmap F2 (PoC Trial Balance) / F3 (General Ledger) |
| D3 | Widget Tagihan (AP jatuh tempo) | Khusus **AP (hutang supplier)** — AR/piutang tidak digabung di widget ini |
| D4 | Goals/Budget Tracker | **Skip total** — tidak masuk scope apapun, tidak perlu model baru |
| D5 | Dark Mode | **Skip** — tidak direncanakan dulu |

**Implikasi**: Wave F-UI ini hanya berisi **3 pekerjaan visual + 1 widget data ringan**, semuanya
dependent pada data yang **sudah ada** di dashboard existing (tidak perlu compute baru dari
MIS Builder/AFR kecuali untuk AP jatuh tempo yang menunggu F3).

---

## 1. Scope Kerja — 4 Item

### F-UI.1 — Card-style Posisi Kas & Bank
**Lokasi**: tab **Detail Keuangan**, section "Posisi Kas & Bank" (existing).

**Kondisi sekarang**: list vertikal, tiap akun = 1 baris dengan ikon bulat kecil + progress bar
tipis di bawah nominal (lihat screenshot Detail Keuangan).

**Target (gaya FinanceFlow, lihat screenshot "Daftar Akun")**:
- Ubah dari list-row menjadi **grid card** (2–3 kolom, responsive).
- Tiap card: ikon bank/wallet di kiri-atas, nama akun + tipe (Bank/E-Wallet/Kas) di bawah ikon,
  nominal besar-bold di tengah, progress bar tipis "porsi dari total" di bawah.
- Warna card **berbeda per akun** (pastel/soft — bukan warna solid mencolok), agar mudah
  dibedakan sekilas di multi-outlet (Bank BSI, QRIS, Bank Mallengkeri, Kas Mallengkeri,
  Kas Operasional Resto — 5 entitas sudah ada datanya).
- **Tidak ada** tombol edit/delete di card (beda dengan FinanceFlow — data akun bank berasal
  dari `account.journal`/`account.account`, bukan CRUD custom).

**Data source**: TIDAK BERUBAH — reuse query yang sudah menghasilkan data "Posisi Kas & Bank"
saat ini. Ini murni perubahan template/CSS (OWL component), bukan perubahan `dashboard_data.py`.

**Effort estimasi**: rendah (~2–4 jam) — restyle komponen existing.

---

### F-UI.2 — Sidebar Grouping dengan Section Header
**Lokasi**: sidebar kiri dashboard (semua tab).

**Kondisi sekarang**: 4 menu (Ringkasan Eksekutif, Detail Keuangan, Penjualan & Menu,
Aset & Operasional) list datar di bawah "Laporan", tanpa pengelompokan.

**Target (gaya FinanceFlow, lihat screenshot sidebar "MENU UTAMA / MODUL / BANTUAN")**:
- Tambahkan section header uppercase kecil (abu-abu, huruf kecil-kapital) untuk
  mengelompokkan menu.
- Kelompok yang disarankan:
  - **LAPORAN**: Ringkasan Eksekutif, Detail Keuangan, Penjualan & Menu, Aset & Operasional
    (grup existing, hanya diberi label section)
  - **LAPORAN OCA** *(placeholder, kosong dulu)*: reserved untuk 9 laporan AFR/MIS Builder
    sesuai §G Q2 roadmap ("Sidebar section baru LAPORAN") — supaya saat F2–F6 selesai,
    section ini tinggal diisi, tidak perlu restrukturisasi sidebar lagi.
- **Penting**: section "LAPORAN OCA" ini HANYA styling/struktur kosong sekarang. Isi menu
  baru (Trial Balance, GL, dst) baru muncul saat F2 dst selesai — jangan buat routing/link
  palsu ke halaman yang belum ada.

**Effort estimasi**: rendah (~1–2 jam) — perubahan struktur XML/JS sidebar + CSS grouping.

---

### F-UI.3 — Gauge Score "Status Keuangan"
**Lokasi**: baru — ditempatkan di tab **Ringkasan Eksekutif**, sebelah/bawah card
"Total omzet / Laba bersih / Total transaksi / Rata-rata transaksi" yang sudah ada.

**Kondisi sekarang**: tidak ada skor kesehatan finansial dalam bentuk apapun.

**Target (gaya FinanceFlow, lihat screenshot gauge "98 Healthy")**:
- Circular gauge 0–100, warna berubah sesuai rentang (misal: hijau ≥80, kuning 50–79,
  merah <50) — palet warna ikut token SCSS dashboard yang sudah ada, jangan pinjam warna
  FinanceFlow mentah-mentah.
- Label status teks di bawah angka: "Sehat" / "Perhatian" / "Waspada" (Bahasa Indonesia,
  bukan "Healthy").

**Formula skor — perlu didefinisikan sebelum eksekusi** (bukan sekadar tiru angka FinanceFlow):
Disarankan skor komposit dari 3 komponen yang datanya **sudah tersedia** di dashboard existing:

| Komponen | Bobot (usulan) | Sumber data (sudah ada) |
|---|---|---|
| Margin bersih bulan ini | 40% | "Laba bersih" & "Margin %" di Ringkasan Eksekutif |
| Likuiditas (kas vs beban bulanan) | 30% | "Posisi Kas & Bank" (total) vs "Total Beban" di Detail Keuangan |
| Piutang tak tertagih | 30% | "Piutang Corporate Belum Lunas" (saat ini 0 → skor penuh) |

> **Catatan**: bobot & threshold di atas adalah **usulan awal**, bukan keputusan final.
> Sebelum implementasi, agent harus konfirmasi formula ini ke user (atau pakai default
> di atas jika user tidak keberatan) — supaya angka gauge tidak terkesan "asal tiru
> FinanceFlow" dan benar-benar mencerminkan kesehatan bisnis F&B.

**Data source**: kombinasi 3 angka yang sudah dihitung `dashboard_data.py` saat ini — TIDAK
perlu compute baru, TIDAK perlu tunggu F3/F5 (bisa dikerjakan sekarang, paralel dengan roadmap
utama, karena Cash Flow & P&L "versi ringkas" sudah tersedia di Ringkasan Eksekutif & Detail
Keuangan existing).

**Effort estimasi**: sedang (~4–6 jam) — 1 jam formula/definisi + 2-3 jam komponen visual gauge
(bisa pakai SVG arc atau library ringan) + testing.

---

### F-UI.4 — Widget "Tagihan Jatuh Tempo (AP)"
**Lokasi**: tab **Ringkasan Eksekutif**, sebagai card baru (mirip posisi "Piutang Corporate
Belum Lunas" yang sudah ada di Detail Keuangan, tapi versi hutang/AP).

**Kondisi sekarang**: hanya ada "Piutang Corporate Belum Lunas" (AR). Belum ada tampilan
hutang supplier (AP) yang akan/lewat jatuh tempo.

**Target (gaya FinanceFlow, lihat screenshot "Tagihan Rutin" — tabel Tagihan/Nominal/
Jatuh Tempo/Status/Frekuensi)**:
- Tabel ringkas 5 kolom: **Supplier / Nominal / Jatuh Tempo / Sisa Hari / Status**.
- Baris diurutkan berdasarkan jatuh tempo terdekat, maksimal tampil 5 baris + link
  "Lihat semua" (link ini nanti mengarah ke laporan **Open Items** penuh setelah F3 selesai —
  untuk sekarang bisa nonaktif/disabled dengan tooltip "tersedia setelah laporan Open Items
  aktif").
- Badge warna: kuning untuk "Sisa ≤3 hari", merah untuk "Lewat jatuh tempo", hijau/abu untuk
  status "Lunas" (kalau ditampilkan histori terakhir).
- **TIDAK** ada tombol tandai lunas / edit — ini read-only, karena pelunasan tetap terjadi
  di alur pembayaran Odoo normal (`account.payment`), bukan lewat dashboard.

**Data source**: `account.move.line` dengan filter AP yang belum reconciled + `date_maturity`
— ini adalah subset dari data yang sama dipakai laporan **Open Items** AFR. Karena Open Items
resmi baru masuk scope di F3 (§G Q5), widget ini punya 2 opsi implementasi:

| Opsi | Deskripsi | Kapan bisa mulai |
|---|---|---|
| **A — Query langsung (sementara)** | Tulis query ringan langsung ke `account.move.line` di `dashboard_data.py`, tanpa lewat wizard AFR | Bisa mulai sekarang, paralel dengan roadmap utama |
| **B — Via Open Items resmi** | Tunggu F3 selesai, widget ini narik subset dari hasil compute Open Items AFR (single source of truth) | Setelah F3 |

**Rekomendasi**: mulai dengan **Opsi A** untuk quick win (selaras prinsip dashboard = "quick
view"), lalu **migrasi ke Opsi B** begitu F3 (Open Items) selesai — supaya angka AP di widget
ini dan di laporan Open Items resmi konsisten (hindari 2 sumber data paralel, sejalan dengan
kekhawatiran divergence di §A.2 roadmap utama).

**Effort estimasi**: sedang (~4–6 jam untuk Opsi A) + migrasi kecil nanti saat F3 selesai.

---

## 1b. Item Terbuka — Chart Arus Kas Harian (BELUM DIPUTUSKAN, jangan eksekusi)

**Konteks**: dibahas 12 Sep 2026, referensi chart "Arus Kas (Bulan Ini)" gaya FinanceFlow
(bar/line 3 series: Income/Expense/Net per hari).

**Hasil cek kompatibilitas** terhadap `MIS_report_instance_XLS_report.xlsx` (output instance
"Cash Flow" existing di MIS Builder):

| Aspek | Instance MIS Cash Flow existing | Kebutuhan chart gaya FinanceFlow |
|---|---|---|
| Arah waktu | Forward-looking (Current → +1w s.d. +8w → bulan ke-3/ke-4) | Backward, histori harian bulan berjalan |
| Granularitas | Mingguan lalu bulanan (campur) | Harian, konsisten 1 bulan |
| Angka per kolom | Hanya kolom "Current" berisi transaksi riil (IN/OUT/PERIOD BALANCE); kolom +1w s.d. +8w BALANCE-nya identik (Rp 196.625.553,03 berulang) — proyeksi mingguan belum terisi angka real | Tiap hari harus beda nilai (real movement) |

**Kesimpulan**: instance existing **TIDAK compatible** untuk dipakai langsung sebagai sumber
chart harian gaya FinanceFlow — fungsinya beda (proyeksi likuiditas ke depan, bukan histori
arus kas harian). Memaksakan reuse akan menghasilkan chart yang salah (kolom mingguan flat).

**Opsi jika nanti mau dikerjakan** (belum dipilih, catat saja):
1. Template MIS baru dengan periode harian — di luar scope F4 (F4 hanya integrasi instance
   existing ke shell, bukan bikin template baru).
2. Query langsung `account.move.line` per hari, mirip logic "Tren Omzet Harian" yang sudah
   ada — tanpa lewat MIS Builder.

**Status**: **DITUNDA**. Keputusan user: tunggu F4 (Cash Flow via MIS Builder, integrasi ke
shell) selesai dulu, baru dibahas ulang apakah chart harian ini masih dibutuhkan setelah
proyeksi mingguan MIS Builder tersedia di shell laporan. **Jangan masukkan ke Wave F-UI atau
anggap otomatis bagian dari F4** — ini keputusan terpisah yang menunggu review pasca-F4.

---

## 2. Yang SENGAJA Tidak Dikerjakan di Wave Ini

| Fitur | Alasan skip |
|---|---|
| Riwayat Transaksi (tabel GL/TB gaya FinanceFlow) | Sudah dijadwalkan resmi di F2 (PoC Trial Balance) & F3 (General Ledger) — mengerjakan sekarang akan duplikat kerja saat F2/F3 tiba, dan berisiko pakai pattern data yang berbeda dari shell resmi (`<ReportTable>`) |
| Widget AR jatuh tempo digabung ke widget AP | Keputusan user: AP dan AR dipisah, tidak digabung dalam satu widget — AR (Piutang Corporate) sudah ada wadahnya sendiri di Detail Keuangan |
| Goals/Budget Tracker | Skip total per keputusan user — tidak perlu model `account.budget` atau sejenisnya dibuat |
| Dark Mode | Skip dulu — tidak masuk rencana kerja, bisa dipertimbangkan lagi nanti |
| Chart Arus Kas harian (Income/Expense/Net) | **Ditunda**, bukan skip permanen — lihat §1b. Instance MIS Cash Flow existing tidak compatible untuk reuse langsung; keputusan final menunggu F4 selesai |

---

## 3. Urutan Eksekusi yang Disarankan

1. **F-UI.2** (sidebar grouping) — paling murah, paling rendah risiko, kerjakan duluan
   supaya struktur section "LAPORAN OCA" placeholder sudah siap sebelum F2 dimulai.
2. **F-UI.1** (card Posisi Kas & Bank) — restyle murni, tidak ada ketergantungan.
3. **F-UI.4 Opsi A** (widget AP jatuh tempo, query langsung) — quick win yang punya nilai
   bisnis nyata (F&B multi-outlet perlu tahu hutang jatuh tempo).
4. **F-UI.3** (gauge score) — perlu konfirmasi formula dulu ke user sebelum coding gauge-nya,
   supaya tidak salah asumsi bobot/threshold.

Item 1–3 bisa paralel dengan roadmap utama F0–F8 (tidak saling bergantung). Item 4 butuh
1 putaran konfirmasi formula sebelum eksekusi.

---

## 4. Batasan Wajib (agar tidak melanggar prinsip roadmap utama)

- **Tidak menulis ulang compute OCA** — semua angka gauge/widget ambil dari data yang sudah
  dihitung `dashboard_data.py` atau (untuk F-UI.4 opsi B nanti) dari compute resmi AFR.
- **Tidak menambah CRUD baru** di dashboard (tidak ada tombol edit/delete/tandai-lunas) —
  semua perubahan data tetap lewat alur normal Odoo.
- **Tidak mengubah urutan F0–F8** roadmap utama — wave ini murni tambahan paralel.
- **Palet warna & token visual** tetap ikut SCSS dashboard existing (`.gk-card`, dst) —
  FinanceFlow hanya referensi *layout/struktur*, bukan sumber warna final.

---

## Appendix — Referensi Visual

- Card-style akun: screenshot "Daftar Akun" FinanceFlow (grid 2-3 kolom, warna pastel beda
  tiap card, progress bar "Porsi dari Total").
- Sidebar grouping: screenshot sidebar FinanceFlow ("MENU UTAMA" / "MODUL" / "BANTUAN").
- Gauge score: screenshot mini-dashboard FinanceFlow (lingkaran skor "98 Healthy" hijau).
- Widget tagihan: screenshot "Target & Tagihan" FinanceFlow, bagian "Tagihan Rutin"
  (tabel Tagihan/Nominal/Jatuh Tempo/Status/Frekuensi).
