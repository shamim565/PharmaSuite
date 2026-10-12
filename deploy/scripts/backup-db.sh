#!/usr/bin/env bash
# PharmaSuite — nightly Postgres backup from the db container, with rotation.
# Cron:
#   15 2 * * * /opt/pharmasuite/deploy/scripts/backup-db.sh >> /opt/pharmasuite/backups/backup.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pharmasuite}"
BACKUP_DIR="${BACKUP_DIR:-/opt/pharmasuite/backups}"
DB_USER="${DB_USER:-pharmasuite}"
DB_NAME="${DB_NAME:-pharmasuite}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F_%H%M)

cd "$APP_DIR"
docker compose -f docker-compose.vps.yml exec -T db \
    pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"

find "$BACKUP_DIR" -name '*.sql.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date -Is) backup written: ${DB_NAME}_${STAMP}.sql.gz"
