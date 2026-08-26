# BOOTSTRAP.md — Auto-setup Skills & MCP untuk OpenCode (Odoo 19)

> **Untuk AI agent:** kerjakan langkah-langkah berikut secara berurutan.
> Jalankan setiap perintah, laporkan hasilnya, lanjut ke langkah berikutnya.
> Jika sebuah langkah gagal, gunakan fallback yang tersedia sebelum menyerah.
> Proses ini harus **idempotent** — jika sudah terpasang, lewati.
> Mulai dari root repo ini.

## Langkah 0 — Cek prasyarat

```bash
opencode --version   # harus terpasang
node --version       # dibutuhkan npx untuk skills CLI
```

Jika `opencode` tidak ada, hentikan dan laporkan cara instalasinya.

## Langkah 1 — Install skill global

```bash
npx -y skills add fhidalgodev/odoo-development-skill --global -a opencode
npx -y skills add mart337i/odoo-skills --global -a opencode
npx -y skills add vercel-labs/agent-skills --skill frontend-design --global -a opencode
npx -y skills add figma/mcp-server-guide --skill figma-design-to-code --global -a opencode
```

**Fallback manual** (jika CLI gagal):

```bash
mkdir -p ~/.config/opencode/skills
git clone --depth 1 https://github.com/fhidalgodev/odoo-development-skill /tmp/skill-a
git clone --depth 1 https://github.com/mart337i/odoo-skills                /tmp/skill-b
git clone --depth 1 https://github.com/vercel-labs/agent-skills            /tmp/skill-c
git clone --depth 1 https://github.com/figma/mcp-server-guide              /tmp/skill-d
```

Cari folder yang **memuat `SKILL.md`** di tiap repo (struktur tiap repo beda —
jangan salin root mentah-mentah), lalu salin ke `~/.config/opencode/skills/`.
Untuk skill-c ambil hanya folder `frontend-design`, untuk skill-d ambil hanya
folder `figma-design-to-code`.

> **Catatan pemasangan 26 Agu 2026:** di Codespace ini `npx`/`git`/`sudo` tidak
> tersedia bawaan. Yang berhasil dipakai: unduh tarball via
> `curl https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main`.
> skill-c **di-skip** (folder `frontend-design` tidak ada di repo sumber —
> keputusan user). Dari mart337i/odoo-skills hanya subset Odoo 19 yang dipasang:
> `odoo`, `odoo-19.0`, `odoo-owl`, `odoo-code-review`, `odoo-test-writer`, `odoo-migration`.

## Langkah 2 — Daftarkan Figma MCP (Mode A, opsional)

1. Baca `opencode.json` di root repo (jika ada). **Merge** kunci berikut tanpa
   menghapus konfigurasi lain yang sudah ada. Jika file belum ada, buat baru:

```jsonc
{
  "mcp": {
    "figma": {
      "type": "remote",
      "url": "https://mcp.figma.com/mcp"
    }
  }
}
```

2. Validasi hasilnya JSON valid (`jq . opencode.json` atau setara).
3. **Catatan:** autentikasi (`opencode mcp auth figma`) butuh login browser
   interaktif oleh manusia. JANGAN coba menyelesaikannya sendiri — tandai sebagai
   *"perlu aksi manual user"* di laporan akhir. Jika user memilih Mode B saja,
   langkah ini boleh dilewati tanpa menandai gagal.

> **Status:** Mode B dipilih (26 Agu 2026) — langkah ini dilewati.

## Langkah 3 — Buat skill custom proyek

1. Inspeksi repo ini dulu: lokasi direktori addons, pola nama modul, versi Odoo
   pada manifest, lokasi asset frontend, konfigurasi database/dev.
2. Buat `.opencode/skills/my-odoo-project/SKILL.md` (sesuaikan nama dengan
   proyek), berdasarkan **hasil inspeksi**, bukan tebakan. Frontmatter wajib:

```
---
name: my-odoo-project
description: Standar pengembangan addon Odoo 19 Community di repo ini. Gunakan saat membuat/mengubah modul, view XML, model, security, dan OWL frontend.
---
```

Isi minimal: struktur addon & penamaan modul, aturan `__manifest__.py`
(version 19.0.x.x.x), security (`ir.model.access.csv`), aturan view XML
(inherit, hindari replace view bawaan), frontend OWL + pendaftaran asset,
command verifikasi (`odoo-bin -d <db> -u <module> --stop-after-init`).

> **Status:** sudah dibuat (26 Agu 2026) di `.opencode/skills/my-odoo-project/`.

## Langkah 4 — Buat skill konversi Figma → OWL

Buat `.opencode/skills/figma-to-odoo-owl/SKILL.md` dengan isi persis seperti ini:

```
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
```

> **Status:** sudah dibuat (26 Agu 2026).

## Langkah 5 — Verifikasi

### 5a. Struktur file

Semua folder skill (global & project) harus memuat `SKILL.md`:

```bash
for base in ~/.config/opencode/skills .opencode/skills; do
  [ -d "$base" ] || continue
  for d in "$base"/*/; do
    [ -f "$d/SKILL.md" ] && echo "OK    $d" || echo "GAGAL $d"
  done
done
```

### 5b. Konfigurasi MCP (jika Langkah 2 dikerjakan)

`opencode.json` valid sebagai JSON dan memiliki `mcp.figma.url`.

### 5c. Verifikasi fungsional

Skill hanya aktif di **sesi baru** — perintah ini otomatis membuat sesi baru:

```bash
opencode run "Sebutkan daftar skill yang tersedia padamu saat ini beserta deskripsi singkatnya."
```

**Kriteria lolos:** menyebut minimal odoo development, referensi odoo 19,
frontend-design, figma-design-to-code, my-odoo-project, dan figma-to-odoo-owl.

**Jika gagal:** perbaiki path/frontmatter lalu ulangi 5c sampai lolos.

## Langkah 6 — Laporan akhir

Sajikan ringkasan:
- Tabel: nama skill | lokasi | sumber (CLI/manual) | status OK/GAGAL
- Status MCP Figma: terkonfigurasi ✔ / perlu OAuth manual ⚠ / dilewati (Mode B) ➖
- Kutipan hasil verifikasi fungsional (5c)
- Error yang terjadi dan penyelesaiannya
- Pengingat: sesi TUI/web yang sedang jalan perlu `/new` atau restart agar
  skill baru termuat.

## Cara memakai file ini

- Interaktif : chat agent → *"Baca BOOTSTRAP.md di root repo dan kerjakan seluruh isinya."*
- One-shot   : `opencode run "$(cat BOOTSTRAP.md)"`
- Codespace baru : jalankan salah satu cara di atas setelah container siap.

## Alur harian desain Figma (untuk manusia)

1. Di Figma: pilih frame → Export → tambahkan **SVG** dan **PNG 2x**
2. github.com (browser HP) → repo ini → `design/exports/` → upload keduanya → commit
3. Chat agent:
   > "Baca design/exports/<nama>.svg — implementasikan sebagai komponen OWL
   > sesuai skill figma-to-odoo-owl. Pakai design/exports/<nama>@2x.png sebagai
   > acuan visual."

Opsional (Mode A): sekali saja jalankan `opencode mcp auth figma` (login browser),
lalu cukup tempel URL frame Figma ke chat tanpa upload apa pun.
