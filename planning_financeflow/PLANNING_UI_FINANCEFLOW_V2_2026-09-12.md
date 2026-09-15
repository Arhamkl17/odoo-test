# Planning — Wave F-UI v2: Adaptasi UI FinanceFlow PRO (REVISI, 12 Sep 2026)

> **Status: SUPERSEDES** `PLANNING_UI_ADAPTASI_FINANCEFLOW_2026-09-12.md` (v1).
> v1 ditulis dengan asumsi lama (F2/F3 belum jalan). Faktanya (roadmap §G.3): **laporan OCA
> sudah 9/9 live** — F1 shell 40/40, F2 TB 13/13, F3 GL & VAT 30/30, F5a/F5b 16/16,
> F6 Aged Partner 19/19, Q1(a) kanonik 19/19. Sisa roadmap utama hanya F4 (uji visual
> Cash Flow) & F7 (polish).
>
> Wave ini **paralel, murni presentasi** — tidak menyentuh compute OCA, tidak mengubah
> urutan F0–F8, tanpa CRUD baru. Palet & token tetap dari SCSS dashboard existing.
>
> Referensi visual: 4 screenshot FinanceFlow di folder ini
> (`01_riwayat_transaksi` · `02_mini_dashboard_gauge` · `03_daftar_akun_card` ·
> `04_target_tagihan`) — berlaku sebagai acuan *layout*, bukan sumber warna.

---

## 0. Perubahan keputusan vs v1

| # | v1 | v2 (dokumen ini) | Alasan |
|---|---|---|---|
| D2v | Riwayat transaksi ditolak (F2/F3 belum jalan) | **Keputusan final (diskusi v2)**: riwayat transaksi = **Buku Besar/Journal Ledger di report shell** (secara substansi sudah jadi riwayat transaksi, 3.215 baris ter-uji). Tidak buat widget/halaman duplikat. Pattern tabel FinanceFlow (badge debit merah/kredit hijau, zebra row, nominal) dipakai sebagai **acuan reskin `<ReportTable>` di F7** — didahului filter tanggal dari F-UI.5 | Audit fitur 12 Sep: GL/JL sudah memenuhi fungsi riwayat; duplikasi melanggar positioning R10 |
| D-v1 | Section LAPORAN OCA = **placeholder kosong** | **Langsung diisi 9 laporan** + grouping semantik + deep-link | 9/9 laporan sudah live di registry |
| F-UI.4 | Opsi A (query langsung) → migrasi Opsi B | **Langsung Opsi B** — tarik dari engine Open Items via wrapper `report_actions.py` | F3 selesai → tidak ada fase migrasi, tidak ada risiko divergensi |
| F-UI.3 | Formula skor komposit 40/30/30 | **Batal.** Gauge = reskin murni; angka diambil dari metrik yang **sudah dihitung** engine OCA & sudah tampil di dashboard (binding metrik bisa diganti 1 baris) | Keputusan user: "ini cuma penyajian data / placeholder" |
| — | "Lihat semua" widget AP = disabled + tooltip | **Deep-link aktif** ke halaman Open Items di report shell | Fitur deep-link baru (lihat §F-UI.2) |
| — | (tidak ada di v1) | **F-UI.5 baru: date range picker di report shell** — filter pilih rentang tanggal/bulan eksplisit, pelengkap month picker | Permintaan user 12 Sep; wrapper Python sudah terima date_from/date_to, tinggal sisi JS |

---

## F-UI.2 v2 — Sistem Sidebar Terpadu (DIPERLUAS, dikerjakan paling awal)

### Temuan kondisi sekarang (kode, 12 Sep)
- **Dua sidebar terpisah dengan pola berbeda**:
  - `dashboard.xml` → section "Laporan" (4 tab) + 1 pintu "Laporan Keuangan Lengkap".
  - `report_shell.xml` → 9 laporan **flat tanpa grouping** + link kembali.
- `dashboard.js:openReports()` **hardcoded konteks** (year/month/outlet) tapi tidak bisa
  men-target laporan tertentu; shell selalu buka `activeReport: "trial_balance"`.

### Target (gaya FinanceFlow — section header uppercase kecil abu-abu)
**a. Dashboard sidebar:**
```
MENU UTAMA
  Ringkasan Eksekutif / Detail Keuangan / Penjualan & Menu / Aset & Operasional
LAPORAN OCA
  Laba Rugi · Neraca · Arus Kas            ← grup "ringkasan" (MIS)
  Trial Balance · Buku Besar · Journal     ← grup "mutasi & saldo" (AFR)
  Umur Piutang · Open Items                ← grup "piutang & hutang"
  Laporan PPN                              ← pajak
```
Pintu lama "Laporan Keuangan Lengkap" dihapus (digantikan akses langsung). Ikon per item
sudah ada di `reports_registry.js` (`icon` + `label` Indonesia) — sidebar cukup `import`.

**b. Report shell sidebar** — grouping semantik yang sama (satu sumber: tambahkan field
`group` di tiap entry `REPORTS` + helper `GROUP_ORDER`), jadi kedua sidebar tidak bisa
beda struktur lagi:

| Grup | Laporan |
|---|---|
| RINGKASAN | Laba Rugi (MIS) · Neraca (MIS) · Arus Kas (MIS) |
| MUTASI & SALDO | Trial Balance · Buku Besar · Journal Ledger |
| PIUTANG & HUTANG | Umur Piutang · Open Items |
| PAJAK | Laporan PPN |

**c. Deep-link `openReports(reportKey?)` (modifikasi baru, unlock fitur lain):**
- `dashboard.js`: `openReports(reportKey = null)` → props `initialReport: reportKey`.
- `report_shell.js`: props `initialReport` (optional, default `"trial_balance"`) →
  `state.activeReport` awal + langsung `selectReport()` saat `onWillStart`.
- Manfaat: sidebar dashboard jadi akses langsung 9 laporan; widget AP (F-UI.4) bisa
  punya link "Lihat semua" yang **berfungsi**; konsisten positioning R10
  (dashboard = quick view, shell = laporan penuh).

**Effort**: ~2–3 jam (2 XML sidebar + registry `group` + deep-link JS + CSS section header).
**Risiko**: rendah. `openReports()` lama tetap jalan (param default).

---

## F-UI.1 v2 — Card Posisi Kas & Bank (grid pastel + footer total)

**Lokasi**: tab Detail Keuangan, section "Posisi Kas & Bank" (existing, `dashboard.xml` ±231).

**Target (foto 03 — Daftar Akun)**:
- List vertikal → **grid card responsive** (3 kolom desktop, 2 tablet, 1 mobile).
- Tiap card: ikon bulat (fa-bank / fa-qrcode / fa-money sesuai tipe journal), nama akun +
  tipe, **nominal besar-bold** di tengah, progress bar tipis "Porsi dari Total" + %.
- Background **pastel berbeda per akun** — diturunkan dari token palet existing
  (`CHART_COLORS` → versi alpha ~8–12% + border kiri aksen 3px), BUKAN warna baru.
- 5 entitas live: BSI 151,8jt · QRIS 92,0jt · Bank Mallengkeri 17,9jt · Kas Mallengkeri
  8,8jt · Kas Operasional 2,8jt (data `dashboard_data.py` **tidak disentuh**).
- Footer section: chip "Total Kas & Bank" (sudah ada datanya, tinggal render).
- **Tanpa** tombol edit/delete (beda dengan foto 03 yang ada ikon pensil/trash di OVO).

**Effort**: ~2–3 jam (template + SCSS; JS hanya getter mapping warna).

---

## F-UI.3 v2 — Gauge "Status Keuangan" (reskin murni)

**Lokasi**: tab Ringkasan Eksekutif, sebelah baris KPI Total Omzet / Laba Bersih /
Total Transaksi / Rata-rata.

**Target (foto 02 — gauge "98 Healthy")**:
- Gauge circular SVG (arc 270°, stroke rounded, animasi fill saat load) + angka besar di
  tengah + label status Indonesia di bawah: "Sehat" / "Perhatian" / "Waspada".
- **Sumber angka = metrik yang sudah dihitung engine OCA dan sudah tampil di dashboard**
  (sesuai keputusan user: ini penyajian ulang, bukan rumus baru). Binding default:
  **Margin bersih %** (sudah ada di payload `summary` hasil compute MIS P&L kanonik).
  Binding-nya satu konstanta di JS — ganti metrik lain = ganti 1 baris, tanpa sentuh backend.
- Threshold warna sebagai **konstanta presentasi** di JS (mis. ≥8% hijau / 5–8% kuning /
  <5% merah untuk margin) — jelas ditandai komentar "placeholder presentasi, bukan
  keputusan bisnis", mudah diubah nanti.
- Warna pakai token semantik SCSS existing (success/warning/danger), bukan warna FinanceFlow.

**Effort**: ~3–4 jam (1 komponen OWL kecil `gauge.js/xml` + wiring di tab summary).

---

## F-UI.4 v2 — Widget "Tagihan Jatuh Tempo (AP)" (langsung dari engine Open Items)

**Lokasi**: tab Ringkasan Eksekutif, card baru (posisi sejajar "Piutang Corporate").

**Target (foto 04 — tabel Tagihan Rutin)**:
- Tabel 5 kolom: **Supplier / Nominal / Jatuh Tempo / Sisa Hari / Status**, urut jatuh
  tempo terdekat, **maks 5 baris**.
- Badge: kuning "Sisa ≤3 hari" · merah "Lewat tempo" · abu "Belum jatuh tempo".
- **Read-only total** — pelunasan tetap lewat `account.payment` alur normal Odoo.
- Footer: link **"Lihat semua →"** = deep-link `openReports("open_items")` (berfungsi
  berkat F-UI.2c) — menggantikan link disabled versi v1.

**Data source (Opsi B langsung)**: wrapper `report_actions.py::get_report_data("open_items")`
— engine AFR Open Items resmi, satu sumber kebenaran dengan halaman laporannya.
**Terverifikasi review 12 Sep**: payload adapter `_adapt_open_items` SUDAH memuat semua
yang dibutuhkan widget — `partner`, `due` (= date_maturity), `original`, `open` (sisa).
Sisa hari dihitung client-side dari `due` vs hari ini. Satu-satunya yang belum ada: penanda
**AP vs AR** per baris (payload memuat semua open items, kode akun saja tidak cukup robust
untuk memilah) → tambahan kecil di adapter wrapper (bukan compute OCA): tag `kind:
"ap"|"ar"` per baris dari `account_type` akun — metadata presentasional, angka tidak
berubah, invariant F3 tetap dijaga (regression test di-run ulang).

**Catatan data**: AR saat ini 0 (Fase 6) — widget ini khusus **AP/hutang supplier**
(keputusan D3: AP dan AR tidak digabung; AR sudah punya wadah sendiri di Detail Keuangan).
Periode tanpa bill jatuh tempo → empty state rapi ("Tidak ada tagihan jatuh tempo"), bukan 0 palsu.

**Effort**: ~3–4 jam (adapter presentational + card XML + badge CSS + deep-link).

---

## F-UI.5 — Date Range Picker di Report Shell (BARU, permintaan user)

**Lokasi**: header report shell (`report_shell.xml`), di samping/complement month picker existing.

**Latar**: month picker (‹ Agustus 2026 ›) hanya bisa memilih 1 bulan penuh. Kebutuhan riwayat
transaksi (GL/Journal) sering perlu rentang custom — mis. 15 Agu – 10 Sep, atau Q3 penuh.

**Target**:
- Tombol/kontrol rentang: **custom date range** (date_from & date_to bebas) — input date
  native browser cukup (bukan library tambahan), styled dengan token SCSS existing.
- **Preset cepat**: Bulan Ini · Bulan Lalu · YTD · 30/90 Hari Terakhir (chip kecil di bawah
  kontrol; yang dipilih ter-highlight).
- Mode: default tetap **month picker** (perilaku lama utk semua laporan); toggle ke
  **"Rentang Kustom"** hanya bila user butuh. State di shell saja — tidak diwariskan
  balik ke dashboard.
- Wrapper Python (`get_report_data`) **sudah menerima date_from/date_to** — perubahan murni
  di JS/XML/SCSS shell; semua laporan otomatis kebagian (GL, JL, TB, dst).
- **Terverifikasi review 12 Sep**: jalur MIS juga sudah siap — `_apply_mis_period`
  men-sinkron kolom periode dari filter shell untuk ketiga pola instance: Cash Flow
  (kolom-1 fix = rentang shell), P&L (kolom Bulan = rentang; YTD = 1 Jan tahun date_to
  s.d. date_to), Neraca (per akhir bulan filter vs bulan sebelumnya). Backend benar-benar
  0 baris.
- **Catatan semantik kolom MIS** (ditampilkan apa adanya, bukan bug): dengan rentang
  kustom, kolom "YTD" P&L tetap berarti 1 Jan s.d. date_to (bukan awal rentang), dan
  kolom pembanding Neraca tetap "bulan lalu" relatif thd date_to → label kolom di shell
  dibuat dinamis mengikuti mode filter (bulan vs rentang) agar tidak menyesatkan.
- Label bulan di header shell (`monthLabel`) ikut berganti jadi teks rentang
  (mis. "15 Agu – 10 Sep 2026") saat mode kustom aktif.
- Guard: date_from > date_to → validasi inline merah, tidak fetch; rentang > 1 tahun →
  konfirmasi (GL bisa puluhan ribu baris; paging 50/halaman sudah ada tapi tetap dijaga).

**Effort**: ~2–3 jam (state + kontrol XML + preset + CSS; backend 0 baris).

---

## Urutan eksekusi (revisi)

| # | Item | Effort | Kenapa urutan ini |
|---|---|---|---|
| 1 | **F-UI.2** sidebar terpadu + deep-link | 2–3 j | Fondasi: F-UI.4 butuh deep-link; shell & dashboard jadi satu pola |
| 2 | **F-UI.1** card kas & bank | 2–3 j | Restyle murni, paling rendah risiko (paralel dgn 1) |
| 3 | **F-UI.3** gauge reskin | 3–4 j | Komponen baru kecil, independen (paralel) |
| 4 | **F-UI.5** date range picker shell | 2–3 j | Independen kecil; nilai besar utk GL/JL riwayat transaksi |
| 5 | **F-UI.4** widget AP | 3–4 j | Butuh deep-link (item 1) + verifikasi payload open_items |

Total ± 12–17 jam kerja. Item 1–4 bisa sebagian besar paralel; item 5 terakhir.

## Audit fitur "sudah ada vs belum ada" (dasar keputusan, 12 Sep)

| Fitur FinanceFlow | Kondisi existing | Klasifikasi |
|---|---|---|
| KPI row + sparkline | ✅ 4 KPI card + vs bulan lalu | Sudah ada |
| Gauge "98 Healthy" | Datanya ada (margin dari MIS), komponen visual belum | Build visual baru (F-UI.3) |
| Arus kas (uang masuk/keluar/net) | ✅ Card arus kas existing | Sudah ada |
| AI Insight | ✅ "Ringkasan Otomatis" (narrative) | Sudah ada |
| Donut pengeluaran | ✅ Bar list "Breakdown Beban Usaha" | Sudah ada (donut opsional) |
| Card grid saldo akun | List vertikal "Posisi Kas & Bank" | Reskin (F-UI.1) |
| Sidebar grouping | Struktur ada, 2 section | Modify (F-UI.2) |
| Tagihan jatuh tempo (AP) | Engine Open Items live; card AR existing sebagai pattern | Build baru (F-UI.4) |
| Riwayat transaksi | = GL/Journal Ledger di shell (live, teruji) | Tidak dibuat — reskin `<ReportTable>` di F7 + filter F-UI.5 |
| Date range custom | Month picker only; wrapper sudah terima date range | Build baru kecil (F-UI.5) |

## Batasan wajib (warisan v1 + roadmap)

- Tidak menulis ulang compute OCA — semua angka dari `dashboard_data.py` (data existing)
  atau wrapper `get_report_data()` (engine resmi).
- Tidak ada CRUD baru di dashboard; read-only semua.
- Tidak mengubah urutan F0–F8; wave ini paralel & kosmetik.
- Token visual dari SCSS existing (`.gk-card`, semantic colors); FinanceFlow = acuan layout.
- **Gate uji visual**: seperti F3/F6/Q1(a) — setelah selesai perlu restart server PID 1 +
  upgrade modul + uji visual browser (belum bisa dari sisi agent).

## Yang tetap tidak dikerjakan (warisan v1, tidak berubah)

Riwayat transaksi sebagai item mandiri (masuk F7 sebagai reskin `<ReportTable>`),
Goals/Budget tracker (skip total), Dark mode (skip), Chart arus kas harian (ditunda
menunggu pasca-F4 — §1b v1 tetap berlaku).
