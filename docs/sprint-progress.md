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

---

## Sprint — Medicine catalog normalization & batch management

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Catalog masters**: `Generic`, `Manufacturer`, `MedicineCategory` (self-nesting), `Unit` (count/weight/volume) with CRUD APIs, search/filters, audit logging.
- **Medicine normalization**: FKs for generic/manufacturer/category/base unit replacing denormalized text fields; new flags `rx_required`, `cold_chain`, `no_batch`; `shelf_life_months`, `near_expiry_days`.
- **Staged migration**: 0002 add models/fields → 0003 backfill masters from legacy text (`testserver`-safe, pure `RunPython`) → 0004 remove legacy fields and rename FKs. Verified `makemigrations --check` clean.
- **Barcodes**: `MedicineBarcode` with unique barcode; single-barcode write support on medicine serializer; duplicate barcode and duplicate SKU rejected with field errors.
- **Pack conversions**: `MedicineUnitConversion` (factor to base, purchase/sale defaults), nested endpoint `GET/POST /medicines/{id}/conversions/`, plus `PATCH/DELETE /medicines/conversions/{id}/`; duplicate conversion returns `CONVERSION_EXISTS`.
- **Batches**: `MedicineBatch` with branch + medicine + batch number + expiry uniqueness, mfg/expiry validation, expiry required for batch-tracked medicines, auto-`EXPIRED` for past expiry, opening quantities (`qty_received_total ≥ qty_on_hand ≥ 0`), branch-scoped list, status/expiry/search filters.
- **Audit fix**: audit snapshots now use `DjangoJSONEncoder` (UUID/Decimal/datetime safe).
- **Frontend**: new `/catalog` masters page (tabs: generics, manufacturers, categories, units), new `/batches` page (filters + create + expiry countdown badges), items page upgraded (FK selects, barcode, flags, inline conversions manager), nav updated (desktop + mobile).

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Backend smoke script (20 checks: masters, backfill, FK update, duplicate barcode/SKU, conversions, batches) | ✅ 20/20 |
| Duplicate barcode / SKU rejected with 400 | ✅ |
| Duplicate batch identity rejected; expiry required; past-expiry auto `EXPIRED` | ✅ |
| Live HTTP: login, batch list, medicine FK shape, conversions | ✅ |
| Frontend routes `/login /items /batches /catalog` served | ✅ HTTP 200 |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (10 routes) | ✅ |

### Key endpoints
- `GET/POST /api/v1/generics/`, `/manufacturers/`, `/medicine-categories/`, `/units/`
- `GET/POST /api/v1/medicines/` (FK filters + search incl. barcode)
- `GET/POST /api/v1/medicines/{id}/conversions/`, `PATCH/DELETE /api/v1/medicines/conversions/{id}/`
- `GET/POST /api/v1/batches/` (filters: branch, medicine, status, batch number, expiry ordering)

### Key screens
- `/catalog` (masters admin), `/batches` (batch & expiry), `/items` (updated catalog with conversions)

### Migrations
- `catalog.0002` (masters + fields), `catalog.0003` (data backfill), `catalog.0004` (cleanup/rename), `audit.0002` (JSON encoder)

### Known limitations
- Batch `qty_on_hand` is a direct field until the inventory-ledger sprint makes it ledger-derived; batch create/update requires `STOCK_ADJUST`.
- Category hierarchy UI supports flat creation only (parent editable via API).
- Automated tests deferred per project decision.

### Next
Sprint 3 — Inventory management: append-only `InventoryTransaction` ledger, opening stock, computed balances, stock ledger view, low-stock/out-of-stock/near-expiry/expired reports, negative-stock prevention.

