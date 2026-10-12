#!/usr/bin/env bash
# PharmaSuite — nightly Postgres backup (host database), with rotation.
# Run on the VPS; pg_dump comes from the host PostgreSQL install.
#
# Auth: either export PGPASSWORD, or create ~/.pgpass with:
#   echo "127.0.0.1:5432:pharmasuite:pharmasuite:<password>" > ~/.pgpass && chmod 600 ~/.pgpass
#
# Cron:
#   15 2 * * * /opt/pharmasuite/deploy/scripts/backup-db.sh >> /opt/pharmasuite/backups/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/pharmasuite/backups}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-pharmasuite}"
DB_NAME="${DB_NAME:-pharmasuite}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F_%H%M)

pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" \
    | gzip > "$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"

find "$BACKUP_DIR" -name '*.sql.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date -Is) backup written: ${DB_NAME}_${STAMP}.sql.gz"
