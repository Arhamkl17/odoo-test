#!/usr/bin/env bash
# =============================================================================
# BOOTSTRAP CODESPACE BARU — satu perintah untuk menyalakan + memulihkan sistem
# -----------------------------------------------------------------------------
# Tujuan: di codespace/akun GitHub lain yang membuka repo ini, cukup jalankan
#
#     bash scripts/bootstrap_codespace.sh
#
# dan sistem kembali persis seperti backup terakhir (DB + filestore + addons),
# lengkap dengan pembandingan 65 metrik baseline dan 6 test parity.
#
# Urutan kerja:
#   0) nyalakan container (bila `docker` tersedia di dalam container ini) dan
#      pastikan addons terbaca proses Odoo (`chmod a+rX`);
#   1) tentukan sumber backup: argumen > berkas lokal di `backups/` >
#      unduh dari GitHub Release repo ini (BACKUP_URL);
#   2) serahkan seluruh pekerjaan berat ke `scripts/restore_full_system.sh`.
#
# Pemakaian:
#   bash scripts/bootstrap_codespace.sh                       # otomatis
#   bash scripts/bootstrap_codespace.sh /path/Test1.dump      # sumber sendiri
#   BACKUP_URL=<url-zip-lain> bash scripts/bootstrap_codespace.sh
#
# Env:
#   BACKUP_URL=<url>   sumber zip (default: release repo ini)
#   DB_NAME=Test1  DB_HOST=db  DB_PORT=5432  DB_USER=odoo  DB_PASSWORD=odoo
#   FORCE=0            batal bila DB tujuan sudah ada (default 1 = DB diganti)
#   RUN_TESTS=0        lewati 6 test parity
#
# PERINGATAN: default FORCE=1 berarti database yang sudah ada dengan nama sama
# akan DIHAPUS dan diganti isi backup. Jangan jalankan di environment produksi.
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_NAME="${DB_NAME:-Test1}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
DB_PASSWORD="${DB_PASSWORD:-odoo}"
FORCE="${FORCE:-1}"
RUN_TESTS="${RUN_TESTS:-1}"
BACKUP_URL="${BACKUP_URL:-https://github.com/Arhamkl17/odoo-test/releases/download/backup-2026-09-15/Test1_full_2026-09-15.zip}"

export PGPASSWORD="$DB_PASSWORD"
log() { echo "==> $*"; }

# --- 0) lingkungan ---------------------------------------------------------
log "0/3 lingkungan"
if command -v docker >/dev/null 2>&1; then
    (cd "$REPO_DIR" && docker compose up -d)
    log "    docker compose up -d dijalankan"
else
    log "    docker tidak ada di container ini — diasumsikan container sudah jalan"
    log "    (kalau belum: jalankan 'docker compose up -d' di terminal codespace/host)"
fi

# addons wajib terbaca user `odoo`, kalau tidak modul kustom hilang dari daftar
chmod -R a+rX "$REPO_DIR/addons" 2>/dev/null || true

log "    menunggu PostgreSQL $DB_HOST:$DB_PORT siap (maks 180 detik)"
for _ in $(seq 1 90); do
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1" >/dev/null 2>&1; then
        log "    PostgreSQL siap"
        break
    fi
    sleep 2
done
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1" >/dev/null \
    || { echo "ERROR: PostgreSQL belum siap — periksa 'docker compose ps' / log container db"; exit 1; }

# --- 1) sumber backup ------------------------------------------------------
log "1/3 sumber backup"
SOURCE="${1:-}"

if [ -n "$SOURCE" ]; then
    [ -e "$SOURCE" ] || { echo "ERROR: sumber '$SOURCE' tidak ditemukan"; exit 1; }
    log "    dari argumen: $SOURCE"
else
    # berkas lokal: zip bundel terbaru, lalu folder backup, lalu .dump terbaru
    LOCAL_ZIP="$(ls -1t "$REPO_DIR"/backups/*_full_*.zip "$REPO_DIR"/backups/*/*_full_*.zip 2>/dev/null | head -1 || true)"
    LOCAL_DIR="$(ls -1dt "$REPO_DIR"/backups/odoo_"$DB_NAME"_*/ 2>/dev/null | head -1 || true)"
    LOCAL_DUMP="$(ls -1t "$REPO_DIR"/backups/*.dump "$REPO_DIR"/backups/*/*.dump 2>/dev/null | head -1 || true)"

    if [ -n "$LOCAL_ZIP" ]; then
        SOURCE="$LOCAL_ZIP"
        log "    berkas lokal: $SOURCE"
    elif [ -n "$LOCAL_DIR" ]; then
        SOURCE="${LOCAL_DIR%/}"
        log "    folder lokal: $SOURCE"
    elif [ -n "$LOCAL_DUMP" ]; then
        SOURCE="$LOCAL_DUMP"
        log "    berkas lokal: $SOURCE"
    else
        DEST_DIR="$REPO_DIR/backups/_download"
        mkdir -p "$DEST_DIR"
        SOURCE="$DEST_DIR/$(basename "$BACKUP_URL")"
        log "    tidak ada backup lokal — mengunduh dari GitHub Release:"
        log "    $BACKUP_URL"
        curl -fL --retry 3 -o "$SOURCE.part" "$BACKUP_URL"
        mv "$SOURCE.part" "$SOURCE"
        log "    terunduh: $SOURCE ($(du -h "$SOURCE" | cut -f1))"
    fi
fi

# cek ringan agar restore tidak berjalan dengan berkas rusak/HTML error page
case "$SOURCE" in
    *.zip)
        python3 - "$SOURCE" <<'PYEOF'
import sys, zipfile
path = sys.argv[1]
z = zipfile.ZipFile(path)
bad = z.testzip()
if bad:
    sys.exit("ERROR: berkas rusak di dalam zip: %s" % bad)
names = set(z.namelist())
if "dump.sql" not in names:
    sys.exit("ERROR: zip tidak berisi dump.sql (bukan bundel backup?)")
print("    zip utuh: dump.sql + %d berkas filestore" % sum(1 for n in names if n.startswith("filestore/")))
PYEOF
        ;;
    *)
        [ -s "$SOURCE" ] || { echo "ERROR: berkas backup kosong: $SOURCE"; exit 1; }
        log "    berkas  $(du -h "$SOURCE" | cut -f1)"
        ;;
esac

# --- 2) restore ------------------------------------------------------------
log "2/3 restore (DB=$DB_NAME, FORCE=$FORCE, RUN_TESTS=$RUN_TESTS)"
FORCE="$FORCE" RUN_TESTS="$RUN_TESTS" DB_NAME="$DB_NAME" DB_HOST="$DB_HOST" \
DB_PORT="$DB_PORT" DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" \
    bash "$REPO_DIR/scripts/restore_full_system.sh" "$SOURCE"

# --- 3) penutup ------------------------------------------------------------
log "3/3 selesai"
cat <<EOF

    Buka  http://localhost:8069  → pilih database "$DB_NAME".

    Rincian lengkap: RINGKASAN di atas, atau
    - INSPEKSI_SISTEM_2026-09-15.md                 (angka baseline & cara mengulang inspeksi)
    - PLANNING_PERBAIKAN_HASIL_INSPEKSI_2026-09-15.md (status fase F1–F7)
    - backups/_download/                            (zip backup hasil unduhan)
EOF
