#!/usr/bin/env bash
# =============================================================================
# BACKUP PENUH SISTEM ODOO  (database + filestore + master data + transaksi)
# -----------------------------------------------------------------------------
# Membuat satu folder backup yang bisa dipindahkan ke codespace/server lain:
#
#   <BACKUP_ROOT>/odoo_<DB>_<STAMP>/
#     <DB>.dump                     pg_dump format custom (-Fc) -> pg_restore
#     <DB>_full_<STAMP>.zip         bundel gaya Odoo: dump.sql + filestore + manifest
#     dump.sql (di dalam zip)       dump teks biasa (versi-agnostik)
#     filestore/                    attachment & foto produk (data_dir Odoo)
#     master/*.csv                  salinan terbaca-manusia semua tabel master & transaksi
#     baseline_metrics.txt          angka kunci (untuk dibandingkan setelah restore)
#     INFO.txt                      versi Odoo/PostgreSQL, commit git, ukuran, dsb.
#     README_BACKUP.md              cara memulihkan (ikut terbawa bersama folder)
#     SHA256SUMS                    checksum setiap berkas
#
# Pemakaian (jalankan DI DALAM container `odoo`, tempat psql & odoo tersedia):
#   bash scripts/backup_full_system.sh
#   DB_NAME=Test1 BACKUP_ROOT=backups bash scripts/backup_full_system.sh
#
# Env yang bisa diubah:
#   DB_NAME=Test1  DB_HOST=db  DB_USER=odoo  DB_PASSWORD=odoo
#   BACKUP_ROOT=backups      (relatif ke akar repo, atau path absolut)
#   STAMP=2026-09-15_1200    (default: tanggal-jam sekarang)
#   WITH_CSV=1  WITH_METRICS=1  (0 = lewati ekspor CSV / angka baseline)
#   OVERWRITE=1              (izinkan menulis ke folder backup yang sudah ada)
#
# Skrip ini BACA-SAJAR terhadap database (pg_dump + SELECT/COPY saja).
# =============================================================================
set -euo pipefail

DB_NAME="${DB_NAME:-Test1}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
DB_PASSWORD="${DB_PASSWORD:-odoo}"
BACKUP_ROOT="${BACKUP_ROOT:-backups}"
STAMP="${STAMP:-$(date +%F_%H%M)}"
WITH_CSV="${WITH_CSV:-1}"
WITH_METRICS="${WITH_METRICS:-1}"
OVERWRITE="${OVERWRITE:-0}"
DATA_DIR="${DATA_DIR:-/var/lib/odoo}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
case "$BACKUP_ROOT" in
    /*) OUT="$BACKUP_ROOT/odoo_${DB_NAME}_${STAMP}" ;;
    *) OUT="$PROJECT_DIR/$BACKUP_ROOT/odoo_${DB_NAME}_${STAMP}" ;;
esac
FILESTORE="$DATA_DIR/filestore/$DB_NAME"
ZIP_NAME="${DB_NAME}_full_${STAMP}.zip"
WORK="$(mktemp -d /tmp/odoo_backup_XXXX)"
export PGPASSWORD="$DB_PASSWORD"

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

log() { echo "==> $*"; }
ok()  { echo "    OK: $*"; }
warn() { echo "    !! $*"; }

# Menjalankan skrip python di dalam `odoo shell` (sesuai pola resmi proyek).
#   $1 = path skrip python, $2 = (opsional) "NAMA_ENV='nilai'" yang perlu diteruskan
run_odoo_shell() {
    local script="$1" extra_env="${2:-}"
    local cmd="$extra_env odoo shell -d '$DB_NAME' --no-http --db_host '$DB_HOST' --db_port '$DB_PORT' --db_user '$DB_USER' --db_password '$DB_PASSWORD' --log-level=warn"
    if [ "$(id -u)" = "0" ] && id odoo >/dev/null 2>&1; then
        su odoo -s /bin/bash -c "$cmd" < "$script"
    else
        bash -c "$cmd" < "$script"
    fi
}

# --- 0) prasyarat ----------------------------------------------------------
log "0/9 Prasyarat"
for tool in psql pg_dump python3; do
    command -v "$tool" >/dev/null || { echo "ERROR: '$tool' tidak ditemukan di PATH"; exit 1; }
done
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1" >/dev/null \
    || { echo "ERROR: tidak bisa terhubung ke database '$DB_NAME' @ $DB_HOST:$DB_PORT"; exit 1; }
if [ -e "$OUT" ] && [ "$OVERWRITE" != "1" ]; then
    echo "ERROR: folder backup sudah ada: $OUT  (pakai OVERWRITE=1 untuk menimpa)"
    exit 1
fi
rm -rf "$OUT"
mkdir -p "$OUT/master" "$OUT/config"
chmod 755 "$OUT"
ok "database $DB_NAME terjangkau; keluaran -> $OUT"

# --- 1) informasi lingkungan ----------------------------------------------
log "1/9 Info lingkungan"
ODOO_VER="$(odoo --version 2>/dev/null | sed -n 's/^Odoo Server //p' | head -1 || true)"
PG_VER="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SHOW server_version")"
PG_CLIENT_VER="$(pg_dump --version)"
DB_SIZE="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME'))")"
DB_TABLES="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
GIT_REV="$(git -C "$PROJECT_DIR" log -1 --format='%H (%ad)' --date=iso 2>/dev/null || echo 'n/a')"
GIT_DIRTY="$(git -C "$PROJECT_DIR" status --porcelain 2>/dev/null | wc -l)"
{
    echo "tanggal_backup   : $(date -Iseconds)"
    echo "database         : $DB_NAME @ $DB_HOST:$DB_PORT (user $DB_USER)"
    echo "ukuran_database  : $DB_SIZE"
    echo "jumlah_tabel     : $DB_TABLES"
    echo "odoo_server      : ${ODOO_VER:-unknown}"
    echo "postgres_server  : $PG_VER"
    echo "postgres_client  : $PG_CLIENT_VER"
    echo "data_dir         : $DATA_DIR"
    echo "filestore        : $FILESTORE"
    echo "git_commit       : $GIT_REV"
    echo "git_perubahan    : $GIT_DIRTY berkas (lihat 'git status')"
    echo "cara_restore     : bash scripts/restore_full_system.sh \"$OUT\""
} | tee "$OUT/INFO.txt"
[ -f /etc/odoo/odoo.conf ] && cp -a /etc/odoo/odoo.conf "$OUT/config/odoo.conf" || true
[ -f "$PROJECT_DIR/docker-compose.yml" ] && cp -a "$PROJECT_DIR/docker-compose.yml" "$OUT/config/docker-compose.yml" || true

# --- 2) dump database (format custom) -------------------------------------
log "2/9 pg_dump format custom -> $DB_NAME.dump"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -Fc --no-owner --no-privileges -f "$OUT/$DB_NAME.dump"
pg_restore -l "$OUT/$DB_NAME.dump" > "$WORK/dump_toc.txt"
ok "$(du -h "$OUT/$DB_NAME.dump" | cut -f1), $(grep -c '^[0-9]' "$WORK/dump_toc.txt") entri TOC"

# --- 3) dump database (teks biasa, untuk bundel zip) ----------------------
log "3/9 pg_dump teks biasa (dipakai di dalam zip)"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-privileges > "$WORK/dump.sql"
# PG17+ menulis parameter yang ditolak PostgreSQL 15 (server compose ini)
sed -i '/^SET transaction_timeout/d' "$WORK/dump.sql"
ok "$(du -h "$WORK/dump.sql" | cut -f1)"

# --- 4) filestore ---------------------------------------------------------
log "4/9 salin filestore"
if [ -d "$FILESTORE" ]; then
    mkdir -p "$OUT/filestore"
    cp -a "$FILESTORE/." "$OUT/filestore/"
    chmod -R a+rX "$OUT/filestore"   # agar bisa dibaca/diunduh pengguna lain
    FS_FILES="$(find "$OUT/filestore" -type f | wc -l)"
    ok "$FS_FILES berkas, $(du -sh "$OUT/filestore" | cut -f1)"
else
    warn "filestore tidak ada di $FILESTORE (database tanpa lampiran)"
    FS_FILES=0
fi

# --- 5) ekspor master data + transaksi ke CSV ----------------------------
log "5/9 ekspor CSV master & transaksi"
if [ "$WITH_CSV" = "1" ] && command -v odoo >/dev/null 2>&1; then
    MASTER_TMP="$(mktemp -d /tmp/odoo_master_XXXX)"
    chown odoo:odoo "$MASTER_TMP" 2>/dev/null || true
    if run_odoo_shell "$SCRIPT_DIR/export_master_data.py" \
            "MASTER_DIR='$MASTER_TMP'" > "$WORK/master_export.log" 2>&1; then
        cp -a "$MASTER_TMP/." "$OUT/master/"
        chmod -R a+rX "$OUT/master"   # agar bisa dibaca/diunduh pengguna lain
        ok "$(grep -c '^EXPORT|' "$WORK/master_export.log") tabel, $(du -sh "$OUT/master" | cut -f1)"
    else
        warn "ekspor CSV gagal — lihat $OUT/master/_CATATAN.csv bila ada; log:"
        tail -5 "$WORK/master_export.log" || true
    fi
    cp -a "$WORK/master_export.log" "$OUT/master/_LOG_EKSPOR.txt" 2>/dev/null || true
    rm -rf "$MASTER_TMP"
else
    warn "ekspor CSV dilewati (WITH_CSV=$WITH_CSV)"
fi

# --- 6) angka baseline ----------------------------------------------------
log "6/9 rekam angka baseline (untuk verifikasi setelah restore)"
if [ "$WITH_METRICS" = "1" ] && command -v odoo >/dev/null 2>&1; then
    run_odoo_shell "$SCRIPT_DIR/backup_metrics_probe.py" 2>/dev/null \
        | grep '^METRIC|' > "$OUT/baseline_metrics.txt" || true
    ok "$(grep -c '^METRIC|' "$OUT/baseline_metrics.txt" || echo 0) metrik"
else
    warn "baseline dilewati (WITH_METRICS=$WITH_METRICS)"
fi

# --- 7) manifest + bundel zip gaya Odoo ----------------------------------
log "7/9 rakitan zip gaya Odoo ($ZIP_NAME)"
export BKP_DB_NAME="$DB_NAME" BKP_ODOO_VER="${ODOO_VER:-unknown}" BKP_PG_VER="$PG_VER"
export BKP_MANIFEST_OUT="$WORK/manifest.json" BKP_DUMP_SQL="$WORK/dump.sql"
export BKP_FILESTORE_DIR="$OUT/filestore" BKP_EXTRA_DIR="$OUT" BKP_ZIP_OUT="$OUT/$ZIP_NAME"
export BKP_MASTER_JSON="$WORK/modules.json"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT json_object_agg(name, latest_version)::text FROM ir_module_module WHERE state='installed'" \
    > "$BKP_MASTER_JSON" 2>/dev/null || echo '{}' > "$BKP_MASTER_JSON"

python3 - <<'PYEOF'
import json, os, re, zipfile

modules = {}
try:
    with open(os.environ["BKP_MASTER_JSON"]) as fh:
        modules = json.load(fh) or {}
except Exception:
    modules = {}

version = os.environ.get("BKP_ODOO_VER", "unknown")
_major = re.match(r"(\d+\.\d+)", version)
manifest = {
    "odoo_dump": "1",
    "db_name": os.environ["BKP_DB_NAME"],
    "version": version,                      # mis. 19.0-20260908 (build yang dipakai)
    "major_version": _major.group(1) if _major else version,   # mis. 19.0
    "pg_version": os.environ.get("BKP_PG_VER", "unknown"),
    "modules": modules,
}
mpath = os.environ["BKP_MANIFEST_OUT"]
with open(mpath, "w") as fh:
    json.dump(manifest, fh, indent=4, sort_keys=True)

zip_path = os.environ["BKP_ZIP_OUT"]
extra = ["master", "baseline_metrics.txt", "INFO.txt", "README_BACKUP.md", "config"]
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.write(os.environ["BKP_DUMP_SQL"], "dump.sql")
    z.write(mpath, "manifest.json")
    fs = os.environ["BKP_FILESTORE_DIR"]
    if os.path.isdir(fs):
        for root, _dirs, files in os.walk(fs):
            for name in files:
                full = os.path.join(root, name)
                z.write(full, os.path.join("filestore", os.path.relpath(full, fs)))
    base = os.environ["BKP_EXTRA_DIR"]
    for item in extra:
        full = os.path.join(base, item)
        if os.path.isfile(full):
            z.write(full, item)
        elif os.path.isdir(full):
            for root, _dirs, files in os.walk(full):
                for name in files:
                    f = os.path.join(root, name)
                    z.write(f, os.path.relpath(f, base))
print("ZIP|%s|%d berkas|%d bytes" % (zip_path, len(zipfile.ZipFile(zip_path).namelist()),
                                    os.path.getsize(zip_path)))
PYEOF
ok "$(du -h "$OUT/$ZIP_NAME" | cut -f1)"

# --- 8) README + checksum -------------------------------------------------
log "8/9 README_BACKUP.md + SHA256SUMS"
cat > "$OUT/README_BACKUP.md" <<EOF
# Backup Odoo — $DB_NAME ($STAMP)

Dibuat oleh \`scripts/backup_full_system.sh\` dari Odoo ${ODOO_VER:-unknown} /
PostgreSQL $PG_VER. Isi folder ini adalah **seluruh sistem**: struktur database,
seluruh master data, transaksi, lampiran, dan konfigurasi.

| Berkas | Isi |
|---|---|
| \`$DB_NAME.dump\` | dump PostgreSQL format *custom* — dipakai \`pg_restore\` (cara utama) |
| \`$ZIP_NAME\` | bundel gaya Odoo (\`dump.sql\` + \`filestore/\` + \`manifest.json\` + CSV) — bisa dipulihkan lewat halaman *Database Manager* Odoo |
| \`filestore/\` | lampiran & foto produk (data_dir Odoo) |
| \`master/*.csv\` | salinan terbaca-manusia seluruh tabel master & transaksi |
| \`baseline_metrics.txt\` | angka kunci sistem (pembanding setelah restore) |
| \`INFO.txt\` / \`config/\` | versi, commit git, odoo.conf, docker-compose.yml |
| \`SHA256SUMS\` | checksum untuk memastikan berkas tidak rusak saat dipindah |

## Cara memulihkan

1. Siapkan codespace/repo + \`docker compose up -d\` (Odoo 19 + PostgreSQL 15).
2. Salin **folder backup ini** (atau minimal \`*.dump\`) ke dalam repo di mesin baru.
3. Jalankan (di dalam container \`odoo\`):

   \`\`\`bash
   bash scripts/restore_full_system.sh "backups/odoo_${DB_NAME}_${STAMP}"
   \`\`\`

4. Skrip akan menaruh ulang database + filestore, lalu membandingkan angka dengan
   \`baseline_metrics.txt\`. Hasil yang diharapkan: **semua metrik sama** dan
   \`RESULT: ALL METRICS MATCH\`.
5. Buka \`http://localhost:8069\` → pilih database \`$DB_NAME\`.

> Alternatif tanpa skrip: restore \`$ZIP_NAME\` lewat halaman *Database Manager*
> Odoo (login admin → *Database Manager* → *Restore Database*).
EOF

( cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
ok "$(wc -l < "$OUT/SHA256SUMS") berkas di-checksum"

# --- 9) ringkasan --------------------------------------------------------
log "9/9 Selesai"
echo
echo "Folder backup : $OUT"
du -sh "$OUT" | awk '{print "Total ukuran  : " $1}'
find "$OUT" -maxdepth 1 -type f -printf '  %-34f %s bytes\n' | sort
echo
echo "Langkah berikutnya:"
echo "  1) pindahkan folder backup ini ke codespace baru (unduh / scp / git-lfs),"
echo "  2) di sana jalankan: bash scripts/restore_full_system.sh \"<folder backup>\""
echo
echo "Catatan: '*dump' & folder '$BACKUP_ROOT/' di-abaikan git (.gitignore) —"
echo "berkas besar ini TIDAK ikut ter-commit; pindahkan manual."
