#!/usr/bin/env bash
#
# Restore an Odoo backup zip (dump.sql + filestore/ + manifest.json) into the
# docker-compose stack (services: odoo + db, Postgres 15).
#
# Usage:
#   bash scripts/restore_db.sh [backup.zip] [db_name]
#
# Defaults:
#   backup.zip -> Test1_2026-09-10_01-43-12.zip
#   db_name    -> Test1
#
# Env:
#   DB_HOST=db, DB_USER=odoo, DB_PASSWORD=odoo  (see docker-compose.yml)
#
# Notes (validated on 2026-09-10 with Test1_2026-09-10_01-43-12.zip):
#   - dump.sql is a PLAIN SQL dump ("-- PostgreSQL database dump" header),
#     so it must be restored with psql, NOT pg_restore.
#   - The dump contains "SET transaction_timeout" (PG17+ param) which PG15
#     rejects; the script strips that line automatically.
#   - If the DB already exists it is DROPPED first (destructive!).
#
set -euo pipefail

ZIP="${1:-Test1_2026-09-10_01-43-12.zip}"
DB="${2:-Test1}"
DB_HOST="${DB_HOST:-db}"
DB_USER="${DB_USER:-odoo}"
DB_PASSWORD="${DB_PASSWORD:-odoo}"
WORKDIR="$(mktemp -d /tmp/restore_XXXX)"
TMP_MARKER=""

cleanup() { rm -rf "$WORKDIR" "$TMP_MARKER"; }
trap cleanup EXIT

[ -f "$ZIP" ] || { echo "ERROR: $ZIP not found"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 required (unzip not installed in odoo image)"; exit 1; }

export PGPASSWORD="$DB_PASSWORD"

echo "==> 1/6 Extracting $ZIP to $WORKDIR"
python3 - "$ZIP" "$WORKDIR" <<'EOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
z.extractall(sys.argv[2])
print("    entries:", len(z.namelist()))
EOF

[ -f "$WORKDIR/dump.sql" ] || { echo "ERROR: dump.sql not in zip"; exit 1; }

echo "==> 2/6 Detecting dump format"
if head -c 64 "$WORKDIR/dump.sql" | grep -q "PostgreSQL database dump"; then
    echo "    plain SQL dump -> restoring with psql"
    PG_FORMAT=plain
else
    echo "    custom format dump -> restoring with pg_restore"
    PG_FORMAT=custom
fi

echo "==> 3/6 Stripping PG17-only 'SET transaction_timeout' (if present)"
sed -i '/^SET transaction_timeout/d' "$WORKDIR/dump.sql" || true

echo "==> 4/6 Dropping + recreating database '$DB' (DESTRUCTIVE)"
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB';" >/dev/null
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB\";"
psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB\" OWNER $DB_USER TEMPLATE template0 ENCODING UTF8;"

echo "==> 5/6 Restoring dump (takes ~1 min for an 84 MB dump)"
if [ "$PG_FORMAT" = plain ]; then
    psql -h "$DB_HOST" -U "$DB_USER" -v ON_ERROR_STOP=1 -q -d "$DB" -f "$WORKDIR/dump.sql"
else
    pg_restore -h "$DB_HOST" -U "$DB_USER" --no-owner --role="$DB_USER" \
        --exit-on-error -j 4 --dbname="$DB" "$WORKDIR/dump.sql"
fi

echo "==> 6/6 Restoring filestore"
FS_DIR="/var/lib/odoo/filestore/$DB"
mkdir -p "$FS_DIR"
cp -a "$WORKDIR/filestore/." "$FS_DIR/"
chown -R odoo:odoo "$FS_DIR"

echo "==> Verify"
TABLES=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
FILES=$(find "$FS_DIR" -type f | wc -l)
echo "    tables in $DB:      $TABLES"
echo "    filestore files:    $FILES"
echo "DONE. Open http://localhost:8069 and pick database '$DB'."
