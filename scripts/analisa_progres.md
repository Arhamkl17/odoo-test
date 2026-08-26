# Analisa Progres Proyek POS Geprekyukss

> Tanggal: 25 Agustus 2026
> Database: `Test1` (Postgres, host `db`) — Odoo 19 Community di Codespace

---

## 1. Yang Sudah Jadi

### Modul Custom POS (`geprekyukss_pos` v19.0.1.0.0) — ter-install & berjalan

| Fitur | Status | Keterangan |
|---|---|---|
| Level pedas 1–5 per orderline | ✅ Solid | Popup pilihan saat produk ditambahkan; pakai hook resmi `addProductToOrder`; field `spice_level` tersimpan ke DB & teregistrasi di `_load_pos_data_fields` |
| Badge produk (Best Seller / New / Pedas otomatis) | ✅ | Field `pos_badge` + `pos_spicy` di product.template |
| Ikon kategori (emoji preset + upload gambar kustom) | ✅ | Field `pos_category_icon` & `pos_category_icon_image` di pos.category |
| Kartu member di layar kasir | ⚠️ UI saja | Tampilan ada (`member_card.js/xml`), verifikasi WA masih simulasi — OTP asli butuh provider (Fonnte/Wablas/WA Business API) |
| Field poin loyalti | ⚠️ Placeholder | `pos_loyalty_points` manual, belum nyambung ke transaksi |
| Tema visual: branding header, actionpad, grid produk 4 kolom | ✅ | pos_theme.scss |
| Layout responsif full-layar semua ukuran | ✅ | Flag `FULLSCREEN_ALL = true` di fit_width_scale.js; letterbox 16:10 bisa dikembalikan dengan set `false` |

### Data & Migrasi

- 202 produk (199 aktif), 6 kategori POS
- 70 BOM dengan 722 baris komponen (termasuk eksperimen BOM sambal, ada backup JSON)
- COA + metode bayar OVO, update harga massal
- Script import 693 baris (`scripts/import_odoo.py`) + file backup JSON

## 2. Penilaian Umum: **7/10** untuk fase prototipe

Kualitas kode baik:
- Komentar menjelaskan *kenapa*, bukan hanya *apa*
- Hook/extension point resmi Odoo dipakai dengan benar
- Ada catatan kompatibilitas antar-versi (Odoo 17–19)

Kekhawatiran utama bukan di kode, tapi di manajemen risiko (git & backup).

## 3. Yang Mendesak (Risiko)

1. ~~**Kode belum di-commit ke git**~~ → ✅ **SELESAI 25 Agu 2026**: commit pertama
   `a2257d2` sudah di-push ke fork `Bakridev17/Odoo-mv`
2. **Database belum pernah di-backup rutin** → 202 produk + 70 BOM susah payah,
   perlu script/cron dump harian:
   ```bash
   docker compose exec db pg_dump -U odoo postgres > backup.sql
   # atau langsung dari codespace:
   PGPASSWORD=odoo pg_dump -h db -U odoo Test1 > backup_$(date +%F).sql
   ```

## 4. Yang Kurang untuk Rencana Ke Depan

3. **Member masih kosong** — belum ada partner dengan nomor WA; belum ada
   konsep Member ID sungguhan (nomor kartu/tier)
4. **Poin loyalitas belum nyambung ke transaksi** — belum ada logika
   tambah/kurang poin saat order POS dibayar
5. **Pembayaran** — OVO baru sebagai COA; belum dicek apakah sudah jadi
   payment method aktif di konfigurasi POS
6. Belum ada: struk/receipt custom, laporan penjualan harian, shift kasir
7. Tidak ada unit test sama sekali
8. Catatan: modul Loyalty bawaan = versi Enterprise; di Community harus buat sendiri

## 5. Saran Urutan Kerja

| # | Tahap | Isi |
|---|---|---|
| 1 | ✅ Infrastruktur | git setup + push pertama (**selesai**) |
| 2 | Backup | Script backup DB rutin |
| 3 | Member | Model `loyalty.member`, generate member ID, integrasi OTP via provider WA |
| 4 | Poin | Mesin poin: tambah poin per transaksi, redeem di pembayaran |
| 5 | Payment | Payment methods lengkap di POS |
| 6 | Finance | Laporan harian, rekonsiliasi kasir, pemetaan journal |

## 6. Catatan Teknis Penting (environment)

- Odoo berjalan sebagai PID 1 di container ini; DB di host `db` (user/pass: odoo/odoo)
- Upgrade modul tanpa restart server:
  ```bash
  odoo -d Test1 -u geprekyukss_pos \
    --db_host db --db_port 5432 --db_user odoo --db_password odoo \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons \
    --stop-after-init --http-port=8070
  ```
  ("Registry changed, signaling through the database" → server jalan otomatis menyesuaikan)
- Addon ter-mount di `/mnt/extra-addons/geprekyukss_pos` (sinkron dengan workspace)
- Push pakai token: `git push "https://x-access-token:${GITHUB_TOKEN}@github.com/Bakridev17/Odoo-mv" main`
