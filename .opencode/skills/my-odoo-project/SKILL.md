---
name: my-odoo-project
description: Standar pengembangan addon Odoo 19 Community di repo ini (proyek Geprekyukss POS). Gunakan saat membuat/mengubah modul, view XML, model, security, dan OWL frontend.
---

# Proyek: Geprekyukss POS — Odoo 19 Community (addon-only, Docker)

## Struktur & lokasi
- Root kerja: `/workspaces/Odoo-mv`; repo git aktual ada di subfolder `Odoo-mv/`
- Addon custom: `Odoo-mv/addons/` → di-mount ke container sebagai `/mnt/extra-addons`
- TIDAK ADA source framework Odoo di repo — Odoo hanya jalan via Docker
- Modul yang ada: `geprekyukss_pos` (POS custom: spice level & member WA)

## Penamaan modul & manifest
- Nama modul: pola `<nama_client>_<domain>` (contoh: `geprekyukss_pos`)
- `__manifest__.py` WAJIB: `"version": "19.0.X.Y.Z"` (contoh `19.0.1.0.0`), `license: LGPL-3`
- Depends umum modul ini: `point_of_sale`, `pos_restaurant`

## Model (Python)
- Hanya extend via `_inherit` pada model bawaan; belum ada model baru (`models/*.py`, wajib diimpor di `__init__.py`)
- Field POS baru HARUS didaftarkan di `_load_pos_data_fields()` agar terkirim ke sesi POS
- Jika membuat model baru: WAJIB buat `security/ir.model.access.csv` + daftarkan di `data` manifest (repo saat ini belum punya folder security sama sekali)

## View XML
- Selalu inherit (`<xpath expr="..." position="...">`), DILARANG replace/menimpa view bawaan secara utuh
- Patch XML frontend POS memakai tuple di assets manifest:
  `("after", "pos_restaurant/static/src/app/<path_file_core>.xml", "geprekyukss_pos/static/src/app/<path_patch>.xml")`
  — elemen pertama = file asli core, kedua = file patch milik addon

## Frontend OWL
- Komponen: `static/src/app/**`, JS dengan header `/** @odoo-module */`, `import { Component } from "@odoo/owl"`
- Template QWeb: `<t t-name="geprekyukss_pos.NamaKomponen">` (prefix nama modul wajib), dialog pakai `<Dialog>` dari `@web/core/dialog/dialog`
- Override komponen: patch di `static/src/overrides/**` (pola `patch()` milik Odoo)
- SCSS di `static/src/scss/`; registrasi asset di manifest:
  - Backend/umum: `web.assets_backend`
  - POS: bundle `point_of_sale._assets_pos` (urutan file & patch tuple diperhatikan)

## Verifikasi
```bash
cd /workspaces/Odoo-mv/Odoo-mv
docker compose up -d                      # odoo:19 + postgres:15, port 8069
docker compose exec odoo odoo -d Test1 -u <nama_modul> --stop-after-init   # upgrade modul
docker compose logs -f odoo               # cek error
```
- DB yang dipakai script: `Test1`; host dari luar: `http://localhost:8069`
- Setelah ubah JS/XML/SCSS POS: refresh browser POS (atau restart sesi POS); perubahan Python wajib upgrade modul seperti di atas

## Konvensi lain
- Script utilitas one-off (XML-RPC/import data) diletakkan di root `Odoo-mv/` atau `scripts/`, jangan masuk folder addon
- Data import CSV/JSON: `import_data/`; foto produk: `product_photos/`
- File desain Figma export: konvensi `design/exports/` (folder dibuat saat pertama dipakai)
