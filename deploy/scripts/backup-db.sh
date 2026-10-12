#!/usr/bin/env bash
# PharmaSuite — nightly Postgres backup with rotation.
# Cron (as the pharmasuite user):
#   15 2 * * * /opt/pharmasuite/deploy/scripts/backup-db.sh >> /opt/pharmasuite/backups/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/pharmasuite/backups}"
DB_NAME="${DB_NAME:-pharmasuite}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F_%H%M)

pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"
find "$BACKUP_DIR" -name '*.sql.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date -Is) backup written: ${DB_NAME}_${STAMP}.sql.gz"
