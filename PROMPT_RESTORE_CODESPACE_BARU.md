# PROMPT RESTORE — Pindahkan Seluruh Sistem Odoo ke Codespace Baru

**Dokumen ini adalah instruksi siap-tempel (prompt) untuk agen AI di codespace/repo baru.**
(Nama folder backup di bawah mengikuti pola `backups/odoo_<DB>_<tanggal>`; bila nama aslinya
berbeda — mis. bertimestamp jam — pakai folder/berkas yang benar-benar ada.)
Cara pakai: buka repo di codespace baru → tempelkan seluruh isi bagian **PROMPT** di bawah ke agen AI
(atau suruh agen membaca berkas ini: *"ikuti PROMPT_RESTORE_CODESPACE_BARU.md"*).

Backup yang harus ikut dipindahkan (dibuat 15 Sep 2026):
`backups/odoo_Test1_2026-09-15/` — 104 MB, atau satu berkas
`backups/odoo_Test1_2026-09-15/Test1_full_2026-09-15.zip` (28 MB) bila ingin lebih ringkas.

---

## PROMPT

### Peran & tujuan

Kamu adalah agen AI di codespace baru. Tugasmu **memulihkan sistem ERP Odoo ini persis seperti
kondisi terakhir (15 September 2026)** — database, seluruh master data, seluruh transaksi, lampiran,
modul kustom, dan konfigurasi — lalu **membuktikan** bahwa hasilnya sama dengan kondisi asal.

Kerjakan berurutan. Jangan mengubah isi database (tanpa perintah pemilik). Jangan push ke git.

### Konteks sistem yang dipulihkan

| Item | Nilai |
|---|---|
| Repo | `Arhamkl17/odoo-test`, branch `main`, folder kerja `/workspaces/odoo-test` |
| Tumpukan | devcontainer + `docker compose` — service `odoo` (image `odoo:19`) dan `db` (`postgres:15`) |
| Akses | `http://localhost:8069` · port DB `5432` · DB `Test1` · kredensial `odoo` / `odoo` |
| data_dir Odoo | `/var/lib/odoo` → filestore `/var/lib/odoo/filestore/Test1` |
| Isi | 32.700 order POS (2 outlet), 4.054 jurnal terposting, 138 modul terpasang, 205 produk aktif, 100 BOM |
| Modul kustom | `addons/geprekyukss_dashboard` (dashboard/laporan) & `addons/geprekyukss_pos` — **wajib terbaca proses Odoo** |
| Sifat data | portofolio **sintetis** 2 outlet (Pallangga & Mallengkeri), periode 19 Jun – 31 Agu 2026 — bukan data klien nyata |
| Kunci periode | `fiscalyear_lock_date = 2026-08-31` (lihat catatan di bawah) |

### Langkah wajib

**1. Siapkan lingkungan**
```bash
# di akar repo
docker compose up -d            # service db + odoo
docker compose ps               # tunggu sampai keduanya "running"
bash .devcontainer/setup.sh     # pastikan addons terbaca (chmod a+rX) — ini penting
```
Terminal devcontainer sudah berada **di dalam container `odoo`** (di situlah `psql`, `pg_dump`,
`pg_restore`, dan `odoo` tersedia). Semua perintah di bawah dijalankan dari akar repo.

**2. Siapkan berkas backup**

- Idealnya folder backup lengkap `backups/odoo_Test1_2026-09-15/` (berisi `Test1.dump`,
  `Test1_full_*.zip`, `filestore/`, `master/*.csv`, `baseline_metrics.txt`, `SHA256SUMS`).
- Jika pemilik hanya mengunggah **satu berkas** `Test1_full_2026-09-15.zip` (28 MB, berisi
  `dump.sql` + `filestore/` + master CSV + baseline + README), itu **sudah cukup** — taruh di folder
  mana pun di dalam repo.
- Jika tidak ada berkas backup sama sekali: **berhenti dan minta pemilik mengunggah** zip tersebut.
  Repo git saja **tidak** bisa memulihkan transaksi (yang ada di git hanya kode, skrip, addons, dan
  ekspor master sebagian di `import_data/`).
- Bila folder lengkap tersedia, pastikan belum rusak:
  ```bash
  cd backups/odoo_Test1_2026-09-15 && sha256sum -c SHA256SUMS | grep -v ': OK$' ; cd -
  ```

**3. Pulihkan** (skrip menangani seluruh seluk-beluk: buang parameter `SET transaction_timeout`
yang ditolak PostgreSQL 15, buat ulang DB, restore filestore, lalu bandingkan dengan baseline)
```bash
bash scripts/restore_full_system.sh "backups/odoo_Test1_2026-09-15"
# atau, bila hanya ada zip:
bash scripts/restore_full_system.sh "/path/ke/Test1_full_2026-09-15.zip"
```
Skrip ini otomatis:
- membuat ulang database `Test1` (butuh `FORCE=1` bila DB sudah ada — akan **menghapus** isinya),
- memulihkan filestore ke `/var/lib/odoo/filestore/Test1` + `chown odoo:odoo`,
- mengecek 59 angka kunci terhadap `baseline_metrics.txt` (harus `RESULT: ALL METRICS MATCH`),
- menjalankan 6 test parity proyek (`RUN_TESTS=0` untuk melewatinya).

**4. Buktikan berhasil** — jalankan ulang verifikasi kapan pun:
```bash
RUN_TESTS=1 bash scripts/restore_full_system.sh "backups/odoo_Test1_2026-09-15"   # (FORCE=1 bila DB ada)
# test parity juga bisa dijalankan manual (pola resmi proyek):
su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db --db_port 5432 \
  --db_user odoo --db_password odoo --log-level=warn" < scripts/test_f5b_bs_parity.py
```

**5. Serahkan ke manusia** — laporkan hasilnya, lalu suruh pemilik membuka
`http://localhost:8069` dan memilih database **Test1**.

### Angka yang harus sama (dari `baseline_metrics.txt`)

| Metrik | Nilai |
|---|---:|
| Order POS / sesi kasir | 32.700 / 146 (semua `done`/`closed`) |
| Omzet POS 72 hari | 2.384.428.500,00 |
| Jurnal terposting / baris jurnal | 4.054 / 9.103 |
| Debit = Kredit | 12.548.642.648,97 |
| HPP Jun / Jul / Agu | 172.739.586,15 · 452.418.667,35 · 449.863.602,21 |
| Persediaan (GL = sub-ledger stok) | 241.605.391,06 |
| Total aset · laba YTD | 2.078.408.511,77 · 1.116.802.388,28 |
| Produk aktif / menu POS / BOM (+baris) | 205 / 103 / 100 (+940) |
| Vendor (+baris harga) | 8 (+52) |
| Modul terpasang / kunci periode | 138 / 2026-08-31 |
| Modul kustom | `geprekyukss_dashboard=installed`, `geprekyukss_pos=installed` |

Keberhasilan penuh = **59/59 metrik sama** dan **6/6 test parity** `ALL PASS`
(`test_f2_tb_crosscheck`, `test_f5_pl_parity`, `test_f5b_bs_parity`, `test_f6_aged_partner`,
`test_report_actions`, `test_beranda_overhaul`).

### Kalau ada masalah

| Gejala | Sebab & tindakan |
|---|---|
| `ERROR: unrecognized configuration parameter "transaction_timeout"` | klien PostgreSQL di image (18.x) lebih baru dari server (15.x). Pakai skrip restore (sudah menyaring baris itu). Manual: `pg_restore -f - dump | sed '/^SET transaction_timeout/d' \| psql -v ON_ERROR_STOP=1 -d Test1` |
| `KeyError`/`field does not exist` untuk field modul kustom, modul hilang dari daftar | addons tidak terbaca proses Odoo (izin berkas). Jalankan `bash .devcontainer/setup.sh` (`chmod -R a+rX addons`), lalu `docker compose restart odoo` |
| Filestore/gambar produk tidak muncul | pastikan `/var/lib/odoo/filestore/Test1` berisi berkas & dimiliki `odoo:odoo` |
| Database tidak muncul di halaman login | *Database Manager* (`http://localhost:8069/web/database/manager`) atau pastikan `list_db = True` di `/etc/odoo/odoo.conf` |
| Entri baru bertanggal ≤ 31 Agu 2026 malah masuk September | **normal**: periode 19 Jun–31 Agu 2026 terkunci (`fiscalyear_lock_date`). Odoo 19 menggeser tanggal entri baru ke setelah tanggal kunci. Untuk koreksi periode lama: `UNLOCK=1` lewat `scripts/perbaikan_12_jejak_audit.py`, kerjakan, lalu `LOCK=1` lagi |
| `database "Test1" already exists` dari skrip restore | memang ada pengaman: tambahkan `FORCE=1` **hanya bila kamu yakin ingin menimpa** database itu |

### Batasan (jangan dilanggar)

1. **Jangan ubah data**: tanpa perintah pemilik, tidak ada `INSERT/UPDATE/DELETE`, tidak menjalankan
   skrip `scripts/perbaikan_*.py`, `scripts/reset_semua_*.py`, atau `scripts/fase*_execute.py`.
2. **Jangan menomori ulang jurnal** (`perbaikan_12_jejak_audit.py` mengubah 146 nomor POS) kecuali diminta.
3. Periksa keadaan itu **read-only**: `psql` (SELECT) dan `odoo shell` untuk pembacaan/uji.
4. Jangan `git push`, jangan hapus `backups/`, jangan `docker compose down -v` (menghapus volume DB!).

### Konteks tambahan (baca bila perlu mendalami)

| Berkas | Isi |
|---|---|
| `INSPEKSI_SISTEM_2026-09-15.md` | hasil inspeksi read-only menyeluruh + baseline angka + cara mengulang inspeksi |
| `PLANNING_PERBAIKAN_HASIL_INSPEKSI_2026-09-15.md` | rencana & status fase perbaikan (F1–F7) |
| `RINGKASAN_PERBAIKAN_F1_F2_2026-09-15.md`, `RINGKASAN_PERBAIKAN_F3_2026-09-15.md` | ringkasan perbaikan yang sudah selesai (HPP sub-resep, persediaan, penomoran jurnal, vendor) |
| `backups/.../README_BACKUP.md`, `INFO.txt` | detail isi backup, versi Odoo/PostgreSQL, commit git saat backup |
| `backups/.../master/*.csv` | seluruh tabel master & transaksi dalam CSV (produk, BOM, harga, COA, vendor, POS, jurnal, stok) |

Fase yang **masih terbuka** (belum dikerjakan, jangan dikerjakan tanpa keputusan pemilik):
**F4** register aset tetap OCA · **F5** alur picking & atribusi lokasi produksi per outlet ·
**F6** label "data demo/portofolio sintetis" + recon vs laporan klien nyata ·
**F7** kerapian modul OCA/data/UI (termasuk hapus DB sisa `tmp_cost_snap`).

### Laporan yang diharapkan darimu

1. Ringkasan: berhasil/gagal, lama proses, nama database & URL.
2. Tabel 59 metrik baseline vs setelah-restore (dari keluaran skrip) — sebutkan bila ada yang berbeda.
3. Hasil 6 test parity (masing-masing `ALL PASS` / daftar kegagalan).
4. Lokasi berkas backup yang dipakai + hasil `sha256sum -c`.
5. Bila ada yang tidak bisa dipulihkan (mis. zip tidak ditemukan), sebutkan tepat apa yang dibutuhkan.

## SELESAI PROMPT
