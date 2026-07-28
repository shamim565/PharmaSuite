# Operations Guide

Operational procedures for running the Medicine Dealer ERP. Commands assume `cd backend` with the environment configured (see `.env.example`).

---

## 1. Service health

| Check | Command / URL |
|---|---|
| API liveness | `GET /api/v1/health/` |
| Deep health (DB, Redis, Celery workers) | `GET /api/v1/health/deep/` |
| Stock cache vs ledger | `uv run python manage.py check_stock_integrity` |
| Customer/supplier/account caches vs ledgers | `uv run python manage.py check_ledger_integrity` |
| Celery heartbeat (every 5 min via beat) | worker logs / deep health |

The deep-health endpoint returns `503` when the database or Redis is unreachable; Celery reports `no workers responding` without failing the request.

## 2. Backup procedure

```bash
cd backend
uv run python manage.py backup_db --output backups
```

- Produces a PostgreSQL custom-format dump (`<db>-YYYYmmdd-HHMMSS.dump`).
- **Copy each backup to encrypted offsite storage** (S3 bucket with versioning/SSE or equivalent) — the local dump alone is not a disaster-recovery plan.
- Retention: 7 daily + 4 weekly + 12 monthly offsite copies minimum.
- Verify backups weekly by restoring the latest dump into a scratch database.

## 3. Restore procedure (destructive)

1. Announce a maintenance window; stop web and Celery workers.
2. `uv run python manage.py restore_db --file backups/<dump> --confirm`
3. Start services and verify:
   - `GET /api/v1/health/deep/` → all `ok`
   - `uv run python manage.py check_ledger_integrity`
   - `uv run python manage.py check_stock_integrity`
   - Smoke: login, open dashboard, open today's sales register.
4. If restore fails, restore the previous nightly dump and escalate.

Quarterly: run a full disaster-recovery drill (restore into a scratch environment + timing against the RTO target).

## 4. Data migration imports (go-live)

CSV templates live in `docs/import-templates/`. Always run with `--dry-run` first.

```bash
uv run python manage.py import_medicines --file ../docs/import-templates/medicines.csv --dry-run
uv run python manage.py import_users --file ../docs/import-templates/users.csv --dry-run
uv run python manage.py import_opening_stock --file ../docs/import-templates/opening-stock.csv --dry-run
uv run python manage.py import_opening_balances --file ../docs/import-templates/opening-balances.csv --dry-run
uv run python manage.py import_opening_accounts --file ../docs/import-templates/opening-accounts.csv --dry-run
```

Import order is fixed: **medicines → users → opening stock → opening balances → opening accounts**. All imports are idempotent (re-running skips existing rows) and post `OPENING` ledger entries — never synthetic invoices.

## 5. User provisioning

- Owner bootstrap: `uv run python manage.py seed_rbac` (creates roles, permission catalog, main branch, default cash account, expense/income categories, owner user).
- New staff: create via the Users screen (assign role(s) + branch(es)); the user receives an invitation and sets their own password.
- Offboarding: deactivate the user (revokes all sessions). Never delete users with history.

## 6. Incident procedure

| Severity | Example | Action |
|---|---|---|
| P1 | API down, DB down, data corruption suspected | Page owner; freeze writes; restore/rollback; postmortem |
| P2 | One module failing (e.g., reports slow), background jobs stalled | Triage within business hours; workaround; fix in next deploy |
| P3 | Cosmetic/isolated issue | Log and schedule |

Escalation contacts, on-call rotation, and the paging provider are configured at deployment time.

## 7. Deployment & rollback

- Deploys run migrations then start the new release (Docker Compose, `web`/`worker`/`beat`).
- Rollback: redeploy the previous image tag; schema changes follow expand/contract so the previous release remains compatible.
- Never edit confirmed documents in the database directly; correct through reversals/returns.

## 8. Dependency & security patching

- Review dependency advisories monthly; patch critical vulnerabilities within 7 days, high within 30.
- Keep `SECRET_KEY`, database credentials, and provider credentials in the environment/secret store — never in the repository.
- Rotate the JWT signing key (forces re-login) if a leak is suspected.
