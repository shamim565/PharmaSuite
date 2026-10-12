# PharmaSuite — Production Deployment (VPS + Vercel)

```
pharmasuite.ruletheday.app       →  Vercel   (Next.js frontend + PWA)
api-pharmasuite.ruletheday.app   →  VPS      (Django + gunicorn, nginx TLS)
                                     VPS      (PostgreSQL native, Redis cache)
```

Both hostnames share `ruletheday.app`, so the refresh cookie is **same-site** —
sessions persist across reloads without any SameSite hacks.

Service user home is `/home/pharmasuite` (tooling caches), the application
lives in **`/opt/pharmasuite`**.

> **Note on static files:** this project has no Django admin and no
> `django.contrib.staticfiles`, so there is **no `collectstatic` step** and no
> separate static file serving. All attachment/media downloads go through
> permission-checked API endpoints (proxied to gunicorn).

---

## 0. DNS (at your registrar)

| Record | Name | Value |
|---|---|---|
| A | `api-pharmasuite` | `<VPS public IP>` |
| CNAME | `pharmasuite` | `cname.vercel-dns.com` |

(Vercel will also show the exact target when you add the domain in step 8.)

## 1. VPS preparation

```bash
# Service user (no login shell); home for tool caches
sudo adduser --system --group --home /home/pharmasuite pharmasuite

# Directories: /home for tooling, /opt for the application
sudo mkdir -p /home/pharmasuite /opt/pharmasuite
sudo chown -R pharmasuite:pharmasuite /home/pharmasuite /opt/pharmasuite
```

Check what's free before continuing:

```bash
ss -ltnp | grep -E '8011|5432|6379'   # 8011 must be free (our gunicorn port)
redis-cli -n 6 ping                    # must not be used by your other apps
redis-cli -n 5 ping
```

## 2. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE pharmasuite LOGIN PASSWORD 'CHANGE_ME_STRONG';
CREATE DATABASE pharmasuite OWNER pharmasuite;
SQL
```

## 3. uv, code + dependencies

```bash
# uv, installed system-wide (all users get `uv` on PATH)
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh

# Clone as the service user
sudo -u pharmasuite -H git clone https://github.com/shamim565/PharmaSuite.git /opt/pharmasuite

# Production dependencies (no dev group)
sudo -u pharmasuite -H bash -c 'cd /opt/pharmasuite/backend && uv sync --frozen --no-dev'
```

## 4. Environment file

```bash
sudo -u pharmasuite -H cp /opt/pharmasuite/deploy/env.production.example /opt/pharmasuite/backend/.env
sudo -u pharmasuite -H nano /opt/pharmasuite/backend/.env
```

Fill in:
- `SECRET_KEY` → `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DATABASE_URL` password (from step 2)
- Confirm `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`

## 5. Migrate, seed, sanity-check

```bash
sudo -u pharmasuite -H bash -c 'cd /opt/pharmasuite/backend && uv run python manage.py migrate --noinput'
sudo -u pharmasuite -H bash -c "cd /opt/pharmasuite/backend && OWNER_PASSWORD='CHANGE_ME_OWNER_PW' uv run python manage.py seed_rbac"
sudo -u pharmasuite -H bash -c 'cd /opt/pharmasuite/backend && uv run python manage.py check --deploy'
```

`check --deploy` should report no critical warnings (HSTS/SSL are already
configured and `SECURE_PROXY_SSL_HEADER` is set for the nginx proxy).

## 6. systemd service

```bash
sudo cp /opt/pharmasuite/deploy/systemd/pharmasuite-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pharmasuite-api
systemctl --no-pager --lines=20 status pharmasuite-api   # should be active (running)
curl -s http://127.0.0.1:8011/api/v1/health/             # {"status": "ok", ...}
```

## 7. nginx + TLS

```bash
sudo cp /opt/pharmasuite/deploy/nginx/api-pharmasuite.ruletheday.app.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/api-pharmasuite.ruletheday.app.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api-pharmasuite.ruletheday.app
```

Verify over HTTPS:

```bash
curl -s https://api-pharmasuite.ruletheday.app/api/v1/health/
# {"status": "ok", "service": "pharmasuite-api"}
```

## 8. Vercel (frontend)

1. vercel.com → **Add New → Project** → import `shamim565/PharmaSuite`
2. **Root Directory: `frontend`** (important — monorepo)
3. Framework preset: Next.js (auto-detected)
4. Environment Variables:
   - `NEXT_PUBLIC_API_URL = https://api-pharmasuite.ruletheday.app/api/v1`
   - Set for **Production and Preview**
5. **Domains** → add `pharmasuite.ruletheday.app` (create the CNAME from step 0)
6. Deploy

## 9. Verification checklist

- [ ] `https://api-pharmasuite.ruletheday.app/api/v1/health/` → `{"status":"ok"}`
- [ ] `https://pharmasuite.ruletheday.app` loads the login page
- [ ] Log in with the owner account → **reload the page → still logged in** (30-day session)
- [ ] Upload an attachment on an expense → download it back
- [ ] Open a sales invoice → Download PDF
- [ ] Install the PWA on a phone → opens standalone with the PharmaSuite icon
- [ ] Create a test sale on the phone (field workflow)

## 10. Day-2 operations

```bash
# Deploy new code (after pushing to main):
# One-time: grant the service account permission to restart only this unit —
#   sudo visudo -f /etc/sudoers.d/pharmasuite
#   pharmasuite ALL=(root) NOPASSWD: /bin/systemctl restart pharmasuite-api, /bin/systemctl status pharmasuite-api
sudo -u pharmasuite /opt/pharmasuite/deploy/scripts/deploy.sh

# Logs:
journalctl -u pharmasuite-api -f

# Backups — add to the pharmasuite user's crontab (crontab -u pharmasuite -e):
15 2 * * * /opt/pharmasuite/deploy/scripts/backup-db.sh >> /opt/pharmasuite/backups/backup.log 2>&1
# Media (attachments) — weekly tar, same idea:
30 2 * * 0 tar -czf /opt/pharmasuite/backups/media_$(date +%F).tar.gz -C /opt/pharmasuite/backend media
```

## 11. Later (optional)

**Notifications (Celery worker + beat):** create two more systemd units modeled on
`pharmasuite-api.service`:
- worker: `ExecStart=.../.venv/bin/celery -A config worker -l info`
- beat:   `ExecStart=.../.venv/bin/celery -A config beat -l info`

They use `REDIS_URL` (DB 5) — ensure it doesn't collide with your other apps' Redis DBs.

**Error tracking:** set `SENTRY_DSN` in `backend/.env` and restart the API.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 502 from nginx | gunicorn down → `systemctl status pharmasuite-api`, `journalctl -u pharmasuite-api` |
| Redirect loop | `SECURE_PROXY_SSL_HEADER` missing (this settings.py sets it when `DEBUG=False`) |
| Session lost on reload | frontend must use the `api-pharmasuite` URL, and both hosts under `ruletheday.app` |
| CORS error in browser console | `CORS_ALLOWED_ORIGINS` must be exactly `https://pharmasuite.ruletheday.app` (with scheme) |
| `DisallowedHost` 400 | `ALLOWED_HOSTS` must be the **bare** hostname (no `https://`) |
