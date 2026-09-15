# PROMPT CHAT — Kalimat Siap-Tempel untuk Agen AI di Codespace Baru

**Berkas ini hanya berisi teks untuk disalin.** Buka repo di codespace baru, buka agen AI
(opencode) di terminal, lalu tempelkan isi blok di bawah.

Kalau agennya sudah bisa membaca repo sendiri, cukup satu baris:
*"ikuti PROMPT_RESTORE_CODESPACE_BARU.md"* — dokumen itu memuat jalur cepat, angka baseline,
tabel troubleshooting, dan format laporan yang sama.

---

## Salin blok ini (versi lengkap)

```text
Kamu agen AI di codespace baru untuk repo Arhamkl17/odoo-test (branch main).
Tugas: pulihkan sistem ERP Odoo ini persis seperti backup 15 September 2026,
lalu buktikan hasilnya sama dengan kondisi asal.

Langkah:
1. Jalankan:  bash scripts/bootstrap_codespace.sh
   (skrip ini menyalakan container, memastikan addons terbaca Odoo, mengunduh
    zip backup dari GitHub Release, lalu restore DB + filestore otomatis)
2. Pastikan keluaran berakhir: 65/65 metrik sama (baseline_metrics.txt) dan
   6/6 test parity ALL PASS (test_f2_tb_crosscheck, test_f5_pl_parity,
   test_f5b_bs_parity, test_f6_aged_partner, test_report_actions,
   test_beranda_overhaul).
3. Suruh pemilik membuka http://localhost:8069 lalu pilih database Test1.

Batasan (jangan dilanggar):
- Jangan ubah isi database: tidak ada INSERT/UPDATE/DELETE, jangan jalankan
  scripts/perbaikan_*.py, scripts/reset_semua_*.py, scripts/fase*_execute.py.
- Pemeriksaan hanya read-only (psql SELECT / odoo shell baca).
- Jangan git push, jangan hapus backups/, jangan `docker compose down -v`.
- FORCE=1 hanya dipakai karena ini codespace baru; berhenti dan tanya pemilik
  bila database Test1 di sini ternyata berisi data yang masih dipakai.

Laporkan:
1. Berhasil/gagal + lama proses + nama database & URL.
2. Tabel semua metrik baseline vs setelah restore — sebutkan bila ada yang beda.
3. Hasil 6 test parity (ALL PASS / daftar kegagalan).
4. Lokasi berkas backup yang dipakai + hasil pemeriksaan keutuhan.
5. Bila ada yang gagal dipulihkan, sebutkan tepat apa yang dibutuhkan.

Rincian lengkap ada di PROMPT_RESTORE_CODESPACE_BARU.md — baca bila perlu.
```

## Kalau tidak ingin memakai Release

Zip backup bisa diserahkan manual (unduh dari halaman Release, atau salin dari mesin asal),
lalu arahkan skrip ke berkas itu:

```text
Jalankan: bash scripts/bootstrap_codespace.sh /path/ke/Test1_full_2026-09-15.zip
```

Atau lewat env bila URL-nya berbeda dari default:

```text
BACKUP_URL=<url-zip-lain> bash scripts/bootstrap_codespace.sh
```

## Yang tidak boleh diminta ke agen codespace baru

| Jangan | Sebab |
|---|---|
| Menjalankan `scripts/perbaikan_*.py` | mengubah data produksi/portofolio, bukan tugas pemulihan |
| Menjalankan `scripts/reset_semua_*.py`, `scripts/fase*_execute.py` | menghapus/menulis ulang transaksi |
| `FORCE=1` pada database yang masih dipakai | database bernama sama akan dihapus lebih dulu |
| `git push`, `docker compose down -v` | mengubah remote / menghapus volume database |
