#!/usr/bin/env bash
# =============================================================================
# RESTORE PENUH SISTEM ODOO  (kebalikan `scripts/backup_full_system.sh`)
# -----------------------------------------------------------------------------
# Memulihkan sistem Odoo di codespace/server baru dari folder backup (atau dari
# satu berkas .dump / .zip), lalu MEMBANDINGKAN hasilnya dengan angka baseline
# backup tersebut.
#
# Pemakaian (dijalankan DI DALAM container `odoo`):
#   bash scripts/restore_full_system.sh backups/odoo_Test1_2026-09-15_1200
#   bash scripts/restore_full_system.sh backups/.../Test1.dump
#   bash scripts/restore_full_system.sh backups/.../Test1_full_2026-09-15_1200.zip
#   DB_NAME=Test1 bash scripts/restore_full_system.sh <sumber>
#
# Env:
#   DB_NAME=Test1  DB_HOST=db  DB_PORT=5432  DB_USER=odoo  DB_PASSWORD=odoo
#   FORCE=1       (wajib bila database tujuan SUDAH ada — akan DIHAPUS dulu)
#   RUN_TESTS=1   (jalankan 6 test parity proyek setelah restore; default 1)
#   SKIP_FILESTORE=1  (hanya database, tanpa lampiran)
#
# PERINGATAN: bila database tujuan sudah ada dan FORCE=1, database itu
# DIHAPUS dan diganti isi backup. Pastikan yang dipilih bukan data produksi
# yang masih dipakai.
# =============================================================================
set -euo pipefail

SOURCE="${1:-}"
DB_NAME="${DB_NAME:-Test1}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-odoo}"
DB_PASSWORD="${DB_PASSWORD:-odoo}"
FORCE="${FORCE:-0}"
RUN_TESTS="${RUN_TESTS:-1}"
SKIP_FILESTORE="${SKIP_FILESTORE:-0}"
DATA_DIR="${DATA_DIR:-/var/lib/odoo}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK="$(mktemp -d /tmp/odoo_restore_XXXX)"
export PGPASSWORD="$DB_PASSWORD"

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

log() { echo "==> $*"; }
ok()  { echo "    OK: $*"; }
warn() { echo "    !! $*"; }
fail() { echo "    GAGAL: $*"; }

if [ -z "$SOURCE" ]; then
    cat <<'USAGE'
Pemakaian: bash scripts/restore_full_system.sh <sumber-backup> [--]

  <sumber-backup> salah satu dari:
    - folder hasil backup (berisi <DB>.dump / <DB>_full_*.zip + baseline_metrics.txt)
    - berkas .dump  (format custom pg_dump)
    - berkas .zip   (bundel gaya Odoo: dump.sql + filestore/ + manifest.json)

Jalankan dari dalam container `odoo` (psql, pg_restore, odoo tersedia di sana).
USAGE
    exit 1
fi
SOURCE="$(cd "$(dirname "$SOURCE")" && pwd)/$(basename "$SOURCE")"
[ -e "$SOURCE" ] || { echo "ERROR: sumber '$SOURCE' tidak ditemukan"; exit 1; }

# --- 0) tentukan berkas sumber -------------------------------------------
DUMP_FILE=""
ZIP_FILE=""
BACKUP_DIR=""
BASELINE=""
if [ -d "$SOURCE" ]; then
    BACKUP_DIR="$SOURCE"
    [ -f "$BACKUP_DIR/baseline_metrics.txt" ] && BASELINE="$BACKUP_DIR/baseline_metrics.txt"
    DUMP_FILE="$(find "$SOURCE" -maxdepth 1 -name '*.dump' | sort | head -1 || true)"
    ZIP_FILE="$(find "$SOURCE" -maxdepth 1 -name '*_full_*.zip' | sort | head -1 || true)"
else
    BACKUP_DIR="$(dirname "$SOURCE")"
    case "$SOURCE" in
        *.dump) DUMP_FILE="$SOURCE" ;;
        *.zip)  ZIP_FILE="$SOURCE" ;;
        *) echo "ERROR: jenis berkas tidak dikenali: $SOURCE (harus .dump atau .zip)"; exit 1 ;;
    esac
    [ -f "$BACKUP_DIR/baseline_metrics.txt" ] && BASELINE="$BACKUP_DIR/baseline_metrics.txt"
fi

log "0/7 Sumber backup"
echo "    sumber      : $SOURCE"
echo "    dump custom : ${DUMP_FILE:-<tidak ada>}"
echo "    bundel zip  : ${ZIP_FILE:-<tidak ada>}"
echo "    baseline    : ${BASELINE:-<tidak ada>}"
[ -n "$DUMP_FILE" ] || [ -n "$ZIP_FILE" ] || { echo "ERROR: tidak ada berkas .dump / .zip di sumber"; exit 1; }

for tool in psql python3; do
    command -v "$tool" >/dev/null || { echo "ERROR: '$tool' tidak ditemukan di PATH"; exit 1; }
done
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1" >/dev/null \
    || { echo "ERROR: tidak bisa terhubung ke PostgreSQL di $DB_HOST:$DB_PORT"; exit 1; }

# --- 1) siapkan berkas restore -------------------------------------------
RESTORE_MODE=""
if [ -n "$DUMP_FILE" ] && command -v pg_restore >/dev/null 2>&1; then
    RESTORE_MODE="custom"
    ok "mode custom (pg_restore): $(du -h "$DUMP_FILE" | cut -f1)"
else
    [ -n "$ZIP_FILE" ] || { echo "ERROR: pg_restore tidak ada dan tidak ada berkas .zip sebagai cadangan"; exit 1; }
    RESTORE_MODE="plain"
    log "1/7 membuka bundel zip (dump.sql + filestore)"
    python3 - "$ZIP_FILE" "$WORK" "$SKIP_FILESTORE" <<'PYEOF'
import sys, zipfile
zip_path, work, skip_fs = sys.argv[1], sys.argv[2], sys.argv[3]
z = zipfile.ZipFile(zip_path)
names = z.namelist()
wanted = [n for n in names if n == "dump.sql"]
if skip_fs != "1":
    wanted += [n for n in names if n.startswith("filestore/")]
for extra in ("baseline_metrics.txt", "INFO.txt", "manifest.json", "README_BACKUP.md"):
    if extra in names:
        wanted.append(extra)
z.extractall(work, wanted)
print("    diekstrak %d entri: dump.sql %s, filestore %d berkas, baseline %s" % (
    len(set(wanted)), "ada" if "dump.sql" in names else "TIDAK ADA",
    sum(1 for n in names if n.startswith("filestore/")),
    "ada" if "baseline_metrics.txt" in names else "tidak ada"))
PYEOF
    [ -f "$WORK/dump.sql" ] || { echo "ERROR: dump.sql tidak ada di dalam zip"; exit 1; }
    [ -d "$WORK/filestore" ] && FALLBACK_FILESTORE="$WORK/filestore"
    # kalau zip dipindah sendirian (tanpa folder backup), baseline ikut dari zip
    if [ -z "$BASELINE" ] && [ -f "$WORK/baseline_metrics.txt" ]; then
        BASELINE="$WORK/baseline_metrics.txt"
        ok "baseline diambil dari dalam zip"
    fi
    sed -i '/^SET transaction_timeout/d' "$WORK/dump.sql"
    ok "dump.sql $(du -h "$WORK/dump.sql" | cut -f1)"
fi

# --- 2) cek database tujuan ----------------------------------------------
log "2/7 database tujuan: $DB_NAME @ $DB_HOST:$DB_PORT"
DB_EXISTS="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'")"
if [ -n "$DB_EXISTS" ] && [ "$FORCE" != "1" ]; then
    cat <<EOF
ERROR: database '$DB_NAME' sudah ada di server ini.

Restore akan MENGHAPUS database itu dan menggantinya dengan isi backup.
Bila memang itu yang diinginkan, jalankan ulang dengan:

    FORCE=1 bash scripts/restore_full_system.sh "$SOURCE"

(atau pilih nama database lain: DB_NAME=NamaBaru bash scripts/restore_full_system.sh "$SOURCE")
EOF
    exit 1
fi

# --- 3) hapus + buat ulang database --------------------------------------
log "3/7 buat ulang database $DB_NAME"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -q -o /dev/null -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -q -o /dev/null -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -q -o /dev/null -c \
    "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\" TEMPLATE template0 ENCODING UTF8;"
ok "database kosong siap diisi"

# --- 4) restore data -----------------------------------------------------
log "4/7 memulihkan data (mode $RESTORE_MODE)"
if [ "$RESTORE_MODE" = "custom" ]; then
    # CATATAN PENTING: klien PostgreSQL di image ini lebih baru (18.x) daripada
    # server (15.x) milik docker-compose. pg_dump 18 menuliskan
    # `SET transaction_timeout = 0;` yang TIDAK dikenal PostgreSQL 15 sehingga
    # `pg_restore --dbname` langsung gagal. Karena itu keluaran pg_restore
    # dialirkan lewat sed untuk membuang baris itu, lalu dieksekusi psql.
    pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --no-owner --role="$DB_USER" \
        -f - "$DUMP_FILE" \
        | sed -e '/^SET transaction_timeout/d' \
              -e '/^SET idle_in_transaction_session_timeout/d' \
        | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -v ON_ERROR_STOP=1 -q -o /dev/null -d "$DB_NAME"
else
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -v ON_ERROR_STOP=1 -q -o /dev/null \
        -d "$DB_NAME" -f "$WORK/dump.sql"
fi
TABLES="$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
ok "$TABLES tabel dipulihkan"

# --- 5) restore filestore ------------------------------------------------
log "5/7 memulihkan filestore (lampiran & foto produk)"
if [ "$SKIP_FILESTORE" = "1" ]; then
    warn "dilewati (SKIP_FILESTORE=1)"
else
    SRC_FS=""
    if [ -n "${FALLBACK_FILESTORE:-}" ] && [ -d "${FALLBACK_FILESTORE:-}" ]; then
        SRC_FS="$FALLBACK_FILESTORE"
    elif [ -d "$BACKUP_DIR/filestore" ]; then
        SRC_FS="$BACKUP_DIR/filestore"
    fi
    if [ -n "$SRC_FS" ]; then
        DEST_FS="$DATA_DIR/filestore/$DB_NAME"
        mkdir -p "$DEST_FS"
        cp -a "$SRC_FS/." "$DEST_FS/"
        chown -R odoo:odoo "$DEST_FS" 2>/dev/null || true
        ok "$(find "$DEST_FS" -type f | wc -l) berkas di $DEST_FS"
    else
        warn "filestore tidak ditemukan di sumber (lampiran/foto produk tidak dipulihkan)"
    fi
fi

# --- 6) bandingkan dengan baseline --------------------------------------
log "6/7 verifikasi terhadap angka baseline"
if [ -n "$BASELINE" ] && command -v odoo >/dev/null 2>&1; then
    run_shell() {
        local cmd="odoo shell -d '$DB_NAME' --no-http --db_host '$DB_HOST' --db_port '$DB_PORT' --db_user '$DB_USER' --db_password '$DB_PASSWORD' --log-level=warn"
        if [ "$(id -u)" = "0" ] && id odoo >/dev/null 2>&1; then
            su odoo -s /bin/bash -c "$cmd" < "$1"
        else
            bash -c "$cmd" < "$1"
        fi
    }
    run_shell "$SCRIPT_DIR/backup_metrics_probe.py" 2>/dev/null | grep '^METRIC|' \
        > "$WORK/metrics_now.txt" || true
    # disimpan di akar proyek (bukan di dalam folder backup) supaya
    # SHA256SUMS folder backup tetap valid
    cp -a "$WORK/metrics_now.txt" "$PROJECT_DIR/metrics_setelah_restore.txt" 2>/dev/null || true
    ok "angka setelah restore dicatat di $PROJECT_DIR/metrics_setelah_restore.txt"

    MISMATCH=0
    MISSING=0
    printf '    %-28s %-22s %-22s\n' "METRIK" "BASELINE" "SETELAH RESTORE"
    while IFS='|' read -r _tag key expected; do
        actual="$(grep -m1 "^METRIC|$key|" "$WORK/metrics_now.txt" | cut -d'|' -f3- || true)"
        if [ -z "$actual" ]; then
            printf '    %-28s %-22s %-22s\n' "$key" "$expected" "<TIDAK ADA>"
            MISSING=$((MISSING + 1))
            continue
        fi
        if [ "$key" = "db_name" ]; then
            printf '    %-28s %-22s %-22s\n' "$key" "$expected" "$actual"
            continue
        fi
        if [ "$actual" = "$expected" ]; then
            printf '    %-28s %-22s %-22s\n' "$key" "$expected" "$actual"
        else
            printf '    %-28s %-22s %-22s  <-- BEDA\n' "$key" "$expected" "$actual"
            MISMATCH=$((MISMATCH + 1))
        fi
    done < "$BASELINE"

    echo
    if [ "$MISMATCH" -eq 0 ] && [ "$MISSING" -eq 0 ]; then
        ok "RESULT: ALL METRICS MATCH ($(grep -c '^METRIC|' "$BASELINE") metrik sama)"
    else
        fail "RESULT: $MISMATCH metrik berbeda, $MISSING metrik tidak terbaca"
        fail "sistem mungkin belum pulih sepenuhnya — periksa log di atas"
    fi
else
    warn "dilewati (tidak ada baseline_metrics.txt di sumber, atau perintah odoo tidak ada)"
fi

# --- 7) test parity proyek ----------------------------------------------
if [ "$RUN_TESTS" = "1" ]; then
    log "7/7 test parity proyek (6 berkas di scripts/test_*.py)"
    TESTS="test_f2_tb_crosscheck test_f5_pl_parity test_f5b_bs_parity test_f6_aged_partner test_report_actions test_beranda_overhaul"
    TEST_FAIL=0
    for t in $TESTS; do
        f="$SCRIPT_DIR/$t.py"
        [ -f "$f" ] || { warn "$t.py tidak ada — dilewati"; continue; }
        OUTTXT="$WORK/$t.log"
        run_shell_test() {
            local cmd="odoo shell -d '$DB_NAME' --no-http --db_host '$DB_HOST' --db_port '$DB_PORT' --db_user '$DB_USER' --db_password '$DB_PASSWORD' --log-level=warn"
            if [ "$(id -u)" = "0" ] && id odoo >/dev/null 2>&1; then
                su odoo -s /bin/bash -c "$cmd" < "$1"
            else
                bash -c "$cmd" < "$1"
            fi
        }
        set +e
        ( cd "$PROJECT_DIR" && run_shell_test "$f" ) > "$OUTTXT" 2>&1
        RC=$?
        set -e
        # penanda hasil berbeda antar berkas: "RESULT: ALL PASS" (5 test) dan
        # "SEMUA CHECK BERHASIL" (test_beranda_overhaul, gagal = exit 1)
        if [ "$RC" -eq 0 ] && grep -qE 'RESULT: ALL PASS|SEMUA CHECK BERHASIL' "$OUTTXT"; then
            ok "$t -> $(grep -m1 -E 'RESULT: ALL PASS|SEMUA CHECK BERHASIL' "$OUTTXT") (exit 0)"
        else
            fail "$t -> exit $RC, penanda sukses tidak ditemukan"
            TEST_FAIL=$((TEST_FAIL + 1))
            tail -15 "$OUTTXT" | sed 's/^/    | /'
        fi
    done
    [ "$TEST_FAIL" -eq 0 ] && ok "RESULT: SEMUA TEST PARITY PASS" \
        || fail "RESULT: $TEST_FAIL test tidak pass"
else
    warn "test parity dilewati (RUN_TESTS=$RUN_TESTS)"
fi

echo
echo "Selesai. Buka http://localhost:8069 lalu pilih database '$DB_NAME'."
echo "Bila Odoo sudah terbuka sebelum restore, restart container agar registry dimuat ulang:"
echo "  docker compose restart odoo"
