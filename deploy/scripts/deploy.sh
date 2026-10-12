#!/usr/bin/env bash
# PharmaSuite — pull latest code and restart the API.
# Usage (as the pharmasuite user, or via sudo -u pharmasuite):
#   /srv/pharmasuite/deploy/scripts/deploy.sh
#
# Requires a sudoers rule for the restart (see deploy/README.md §10):
#   pharmasuite ALL=(root) NOPASSWD: /bin/systemctl restart pharmasuite-api, /bin/systemctl status pharmasuite-api
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/pharmasuite}"
BRANCH="${BRANCH:-main}"

if [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
else
    UV="uv"
fi

cd "$APP_DIR"
echo "→ pulling $BRANCH ..."
git pull --ff-only origin "$BRANCH"

cd backend
echo "→ syncing dependencies ..."
"$UV" sync --frozen --no-dev

echo "→ applying migrations ..."
"$UV" run python manage.py migrate --noinput

echo "→ restarting API ..."
sudo systemctl restart pharmasuite-api
sudo systemctl --no-pager --lines=0 status pharmasuite-api || true

echo "✓ deploy complete"
