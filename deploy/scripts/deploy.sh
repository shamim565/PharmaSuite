#!/usr/bin/env bash
# PharmaSuite — pull latest code and rebuild the VPS stack.
# Run on the VPS:  /opt/pharmasuite/deploy/scripts/deploy.sh
# The container entrypoint applies migrations on start.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pharmasuite}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"
echo "→ pulling $BRANCH ..."
git pull --ff-only origin "$BRANCH"

echo "→ rebuilding and restarting the stack ..."
docker compose -f docker-compose.vps.yml up -d --build
docker compose -f docker-compose.vps.yml ps

echo "✓ deploy complete"
