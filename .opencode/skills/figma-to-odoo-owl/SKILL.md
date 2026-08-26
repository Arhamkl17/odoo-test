---
name: figma-to-odoo-owl
description: Konversi desain Figma menjadi komponen OWL 3.x untuk Odoo 19. Gunakan setiap kali user memberi URL Figma, path file export (SVG/PNG), atau meminta implementasi UI dari desain.
---

## Mode A — Via MCP Figma (jika tersedia dan ter-autentikasi)
- Ambil konteks desain lewat get_design_context; perlakukan hasil
  (biasanya React+Tailwind) HANYA sebagai acuan visual
- Tulis ulang sebagai OWL component (XML template + JS + SCSS module milik addon)

## Mode B — Dari file export (jalur utama tanpa MCP)
Jika user memberi PATH FILE (bukan URL Figma):
- Prioritaskan file .svg sebagai sumber data utama: ekstrak warna (hex),
  dimensi, radius, struktur layer, dan konten teks dari XML-nya
- File .png/.jpg .pdf di folder yang sama = acuan visual pembanding
  (.png/.jpg bisa dibaca; abaikan .pdf karena tidak dapat dikirim ke model)
- Abaikan koordinat absolut SVG; terjemahkan layout ke struktur OWL/SCSS
  yang idiomatik (flex/grid), JANGAN absolute-positioning
- Teks yang di-outlined di Figma tidak terbaca dari SVG — minta user
  konfirmasi jika ada teks yang tampak hilang
- Jika hanya PNG yang tersedia (tanpa SVG), kerjakan dari gambar saja
  dan catat di akhir bahwa presisi warna/spacing perlu diverifikasi user

## Aturan konversi (berlaku untuk kedua mode)
- Tailwind class → SCSS sendiri; daftarkan asset di __manifest__.py
  ('web.assets_frontend' untuk portal/website, 'web.assets_backend' untuk backend)
- Reuse komponen/bawaan Odoo sebelum membuat baru
- Warna/spacing map ke variabel SCSS tema Odoo, jangan hardcode hex
- Ikon pakai font ikon bawaan Odoo / fa-* yang sudah tersedia

## Verifikasi
Setelah implementasi: build assets lalu minta user cek hasil via port forward
Odoo (8069). Bandingkan screenshot hasil vs desain.
