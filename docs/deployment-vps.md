# VPS Deployment — Shared Contabo Server (`api-pharmasuite.ruletheday.app`)

Target: the Contabo VPS running Ubuntu 24.04 that already hosts other Docker
stacks (`ruletheday-backend` owns host :80/:443 with its own nginx + certbot;
`movie_reservation_backend` uses :81; `travel-persona` uses :8010; `airport-kiosk`
uses :8012). PharmaSuite's API runs as an isolated Docker project
(`/opt/pharmasuite`) and is reverse-proxied by the existing ruletheday nginx.
The frontend is deployed separately on **Vercel**.

```
Internet :80/:443
   └─▶ ruletheday-backend-nginx-1        (theirs; one appended server block)
         ├── ruletheday.app / api.*      (untouched)
         ├── persona… / dishari…         (other apps, untouched)
         └── api-pharmasuite.ruletheday.app ──▶ pharmasuite-web:8000 (gunicorn)
                                                  ├─▶ host PostgreSQL   (own "pharmasuite" database)
                                                  └─▶ pharmasuite-redis (cache container)

pharmasuite.ruletheday.app ──▶ Vercel (Next.js frontend + PWA)
```

Both hostnames share `ruletheday.app`, so the API refresh cookie is same-site —
30-day sessions persist across reloads.

> **Database:** PostgreSQL runs on the **host** (the same server your
> ruletheday-backend stack uses, with its own `pharmasuite` database). The web
> container reaches it via `host.docker.internal`; there is no database
> container in this stack.

> **No collectstatic:** this project has no Django admin and no
> `django.contrib.staticfiles`. Attachment/media downloads go through
> permission-checked API endpoints; uploads live on the `media_files` volume.

## 1. DNS (Cloudflare)

1. Get the VPS IP: `curl -4 -s ifconfig.me`
2. Cloudflare dashboard → zone **ruletheday.app** → **DNS** → **Records**:

   | Type | Name | Value | Proxy |
   |---|---|---|---|
   | A | `api-pharmasuite` | `<VPS IP>` | **DNS only** (grey) — required so the Let's Encrypt HTTP-01 challenge reaches the origin directly |
   | CNAME | `pharmasuite` | `cname.vercel-dns.com` | per Vercel's instructions |

3. Verify: `dig +short api-pharmasuite.ruletheday.app @1.1.1.1` → the VPS IP.

## 2. First deploy

One-time: create the database + role on the **host** PostgreSQL (no `pg_hba`
changes needed — Docker-bridge access already works for ruletheday-backend):

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE pharmasuite LOGIN PASSWORD '<strong URL-safe password>';
CREATE DATABASE pharmasuite OWNER pharmasuite;
SQL
```

Then:

```bash
ss -ltnp | grep 8013      # free? (loopback debug port; change compose if taken)

mkdir -p /opt/pharmasuite && cd /opt/pharmasuite
git clone https://github.com/shamim565/PharmaSuite.git .

# .env (never committed)
cp deploy/env.production.example .env
chmod 600 .env
nano .env                  # SECRET_KEY + the DATABASE_URL password (must match the role)

docker compose -f docker-compose.vps.yml up -d --build
docker compose -f docker-compose.vps.yml logs --tail=50 web   # migrate output
```

Create the owner account (seeded roles + first user):

```bash
docker compose -f docker-compose.vps.yml exec -e OWNER_PASSWORD='<strong password>' web \
    python manage.py seed_rbac
```

## 3. Verify the stack internally

```bash
# through the loopback binding
curl -fsS http://127.0.0.1:8013/api/v1/health/

# through the shared Docker network, simulating the outer proxy
docker exec ruletheday-backend-nginx-1 \
  wget -qO- --header='Host: api-pharmasuite.ruletheday.app' http://pharmasuite-web:8000/api/v1/health/
```

Expected: `{"status": "ok", "service": "pharmasuite-api"}`.

## 4. TLS certificate (existing certbot container)

```bash
docker exec ruletheday-backend-certbot-1 certbot certonly --webroot \
  -w /var/www/certbot -d api-pharmasuite.ruletheday.app --non-interactive --agree-tos
ls -l /etc/letsencrypt/live/api-pharmasuite.ruletheday.app/
```

The renewal config is written with `authenticator = webroot`, so the container's
renew loop keeps it valid.

## 5. Route the subdomain through the ruletheday nginx

Their nginx mounts a single config file, so append the snippet (versioned in
this repo at `deploy/vps/ruletheday-snippet.conf`) with a backup first:

```bash
cp /opt/ruletheday-backend/nginx/nginx.conf \
   /opt/ruletheday-backend/nginx/nginx.conf.bak-$(date +%F)

# append the contents of deploy/vps/ruletheday-snippet.conf to nginx.conf
# (to replace an existing block, drop it first between the markers:)
#   sed -i '/# BEGIN pharmasuite/,/# END pharmasuite/d' \
#     /opt/ruletheday-backend/nginx/nginx.conf

docker exec ruletheday-backend-nginx-1 nginx -t
docker restart ruletheday-backend-nginx-1
```

`nginx -t` must pass before applying. Restart (not `-s reload`): the config is a
single-file bind mount, so a replaced file keeps its old inode in the container.

## 6. Verify live

```bash
curl -fsS https://api-pharmasuite.ruletheday.app/api/v1/health/
```

Browser checklist:

- `https://pharmasuite.ruletheday.app` loads the login page (Vercel frontend)
- Log in → **reload → still logged in** (30-day session via the same-site cookie)
- Upload an attachment on an expense → download it back
- Open a sales invoice → Download PDF
- Install the PWA on a phone → standalone with the PharmaSuite icon
- Re-check `ruletheday.app` / `api.ruletheday.app` / other apps still respond

## 7. Backups + housekeeping (cron on the VPS)

One-time: let cron authenticate as the `pharmasuite` role (no password prompts):

```bash
echo "127.0.0.1:5432:pharmasuite:pharmasuite:<password>" > ~/.pgpass && chmod 600 ~/.pgpass
mkdir -p /opt/pharmasuite/backups
crontab -e
```

```cron
# 02:15 — nightly Postgres dump (rotates after 14 days)
15 2 * * * /opt/pharmasuite/deploy/scripts/backup-db.sh >> /opt/pharmasuite/backups/backup.log 2>&1

# 02:30 Sundays — attachments volume
30 2 * * 0 docker run --rm -v pharmasuite_media_files:/data -v /opt/pharmasuite/backups:/backup alpine \
    tar -czf /backup/media_$(date +\%F).tar.gz -C /data .
```

Restore (database):

```bash
gunzip -c /opt/pharmasuite/backups/pharmasuite_<stamp>.sql.gz | \
  psql -h 127.0.0.1 -U pharmasuite pharmasuite
```

Keep a copy **off the VPS** (rclone to S3/B2, or `scp` them to your machine
periodically) — a backup on the same disk is not a backup.

## 8. Updates

```bash
/opt/pharmasuite/deploy/scripts/deploy.sh
# or manually: cd /opt/pharmasuite && git pull && docker compose -f docker-compose.vps.yml up -d --build
```

The entrypoint runs `migrate --noinput` on every start; `.env` stays untouched.
If `deploy/vps/ruletheday-snippet.conf` changed in the repo, re-apply the block
(replace between the `# BEGIN/# END pharmasuite` markers) and restart the
ruletheday nginx.

## 9. Vercel (frontend)

1. vercel.com → **Add New → Project** → import `shamim565/PharmaSuite`
2. **Root Directory: `frontend`** (important — monorepo)
3. Framework preset: Next.js (auto-detected)
4. Environment Variables:
   - `NEXT_PUBLIC_API_URL = https://api-pharmasuite.ruletheday.app/api/v1`
   - Set for **Production and Preview**
5. **Domains** → add `pharmasuite.ruletheday.app` (create the CNAME from step 1)
6. Deploy

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `502 Bad Gateway` | `web` container down → `docker compose -f docker-compose.vps.yml ps`, `logs web` |
| `400 DisallowedHost` | `ALLOWED_HOSTS` missing the domain or `localhost` |
| `FATAL: password authentication failed for user "pharmasuite"` | `.env` `DATABASE_URL` password doesn't match the role → `sudo -u postgres psql -c "ALTER ROLE pharmasuite PASSWORD '<new>';"` and update `.env` |
| `connection refused` to `host.docker.internal:5432` | host PostgreSQL not accepting Docker-bridge connections — mirror the ruletheday-backend `listen_addresses`/`pg_hba` setup |
| `could not translate host name "host.docker.internal"` | the compose `extra_hosts` line is missing (needs Docker ≥ 20.10) |
| Session lost on reload (browser) | frontend env must point at `api-pharmasuite…`; both hosts under `ruletheday.app` |
| CORS error in browser console | `CORS_ALLOWED_ORIGINS` must be exactly `https://pharmasuite.ruletheday.app` (with scheme) |
| Redirect loop | `X-Forwarded-Proto` not reaching Django — settings.py sets `SECURE_PROXY_SSL_HEADER` when `DEBUG=False`; verify the snippet is applied |
| `nginx: [emerg]` on restart | snippet references the cert before it exists — issue the cert first (step 4) |
| certbot challenge fails | DNS not propagated, or Cloudflare proxy is orange — set DNS only |
| Attachment upload fails (> 25 MB) | raise `client_max_body_size` in the snippet and restart the ruletheday nginx |
