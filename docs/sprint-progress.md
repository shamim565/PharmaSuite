# Sprint Progress

## Sprint — Full-stack foundation: PostgreSQL, Redis, Celery, Docker Compose, frontend, auth, items API, dashboard

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **PostgreSQL**: env-driven Django settings (`DATABASE_URL`), migrations for accounts/branches/audit/catalog, local dev DB `erp_dev` + Compose `postgres:16`.
- **Redis**: broker/result backend on DB 5 (`redis://localhost:6379/5`) to isolate from other local apps; Compose `redis:7`.
- **Celery**: `config/celery.py`, `apps.common.tasks.heartbeat`, beat schedule (5 min), worker + beat services in Compose. macOS dev note: run worker with `--pool=threads` (celery 5.6 prefork fast-trace bug on darwin); Linux/Docker uses default prefork.
- **Deep health**: `GET /api/v1/health/` and `/health/deep/` report database, Redis and Celery worker status.
- **Backend**: Django 5/6 + DRF, RBAC (9 system roles, 62 permissions), JWT auth with rotating refresh cookies, audit logging, page-number pagination, standard error envelope `{code, message, field_errors, request_id}`, request-id middleware.
- **Items API**: catalog `Medicine` model + CRUD (`/api/v1/medicines/`) with validation, search/filters/ordering, audit on create/update.
- **Dashboard API**: `/api/v1/dashboard/summary/` with branch-scoped user/branch/role/medicine KPIs and placeholders for operational metrics (unlock in later sprints).
- **Next.js frontend**: App Router + TypeScript + Tailwind v4 + TanStack Query; in-memory access token with httpOnly refresh-cookie restore; responsive app shell (desktop sidebar, mobile drawer + bottom nav).
- **Pages**: Login, Dashboard, Items (list/search/create/activate), Users (list/create with roles+branches/activate), Branches (list/create).
- **Docker Compose**: `web` (Gunicorn + migrate + seed on start), `worker`, `beat`, `postgres`, `redis`; backend `Dockerfile` + `.dockerignore`.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| `manage.py check` / `makemigrations --check` | ✅ no issues / no changes |
| `ruff check .` | ✅ all checks passed |
| `next build` (incl. type check) | ✅ 6 routes compiled |
| Login → `/auth/me` (62 perms, MAIN branch) | ✅ |
| Create + search medicine | ✅ `PARA500` |
| Dashboard summary | ✅ users/branches/medicines |
| Unauthorized request | ✅ HTTP 401 |
| Deep health (DB/Redis/Celery) | ✅ all ok |
| Celery heartbeat task round-trip | ✅ `{status: ok}` |

### Key endpoints
- `POST /api/v1/auth/login|refresh|logout/`, `GET /api/v1/auth/me/`
- `GET/POST /api/v1/users/`, `POST /api/v1/users/{id}/activate|deactivate/`
- `GET/POST /api/v1/roles/`, `PUT /api/v1/roles/{id}/permissions/`, `GET /api/v1/permissions/`
- `GET/POST /api/v1/branches/`
- `GET/POST /api/v1/medicines/`
- `GET /api/v1/dashboard/summary/`
- `GET /api/v1/health/`, `GET /api/v1/health/deep/`

### Key screens
- `/login`, `/` (dashboard), `/items`, `/users`, `/branches`

### Migrations
- `accounts.0001_initial`, `accounts.0002_initial`
- `branches.0001_initial`
- `audit.0001_initial`
- `catalog.0001_initial`

### Known limitations
- Automated tests deferred per project decision (backend pytest config is in place for a later hardening sprint).
- Draft/confirmed document workflows, inventory ledger, and financial modules land in later sprints; dashboard operational KPIs are `null`.
- Local dev defaults to API port **8010** (port 8000 on this machine is occupied by another app); frontend `.env.local` matches.
- Celery on macOS requires `--pool=threads` until the upstream prefork fast-trace issue is resolved.

### Next
Sprint 2 — Medicine catalog normalization and batch management (generics, manufacturers, categories, units/conversions, barcodes, batches with expiry), with catalog UI.
