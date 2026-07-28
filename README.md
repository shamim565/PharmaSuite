# Medicine Dealer ERP

Multi-branch medicine distribution ERP.

- `backend/` — Django 5 + DRF + PostgreSQL + Redis + Celery (modular monolith, API-first)
- `frontend/` — Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query/Table + RHF/Zod + Zustand
- `infra/` — Docker Compose for local PostgreSQL/Redis
- `docs/` — requirements, domain model, and sprint progress

## Quick start (local)

```bash
# services (either Docker Compose, or your local Postgres 17 + Redis)
docker compose -f infra/docker-compose.yml up -d
createdb erp_dev            # if not using compose

# NOTE: local dev database runs on port 5433 in this environment
# (Homebrew PostgreSQL 17, `pg_ctl -D /opt/homebrew/var/postgresql@17 -o "-p 5433" start`).
# Postgres.app on 5432 works too — just update DATABASE_URL in backend/.env.

# backend
cd backend
uv sync
cp .env.example .env        # adjust if needed
uv run python manage.py migrate
uv run python manage.py seed_rbac
uv run python manage.py runserver 8010

# celery (macOS dev needs the threads pool; Linux/Docker uses prefork)
uv run celery -A config worker -l info --pool=threads
uv run celery -A config beat -l info

# frontend
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

> Dev API runs on `http://localhost:8010` (frontend `.env.local` matches). Any free port works; update `NEXT_PUBLIC_API_URL` and `CORS_ALLOWED_ORIGINS` together.

Default owner created by `seed_rbac`: mobile `01700000000`, password `Admin@1234` (override with `OWNER_MOBILE` / `OWNER_PASSWORD` env).

## Conventions

- All business rules live in service modules; views/serializers stay thin.
- Money/quantity fields are `Decimal` only.
- Inventory/customer/supplier/account balances derive from append-only ledgers.
- Every mutation on business data is audit-logged.
