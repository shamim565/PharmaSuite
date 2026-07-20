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

---

## Sprint — Inventory management & stock ledger

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Inventory ledger**: `InventoryTransaction` — append-only (model blocks update/delete), entry types (OPENING, PURCHASE, BONUS, SALE, SALES_RETURN, PURCHASE_RETURN, ADJUSTMENT, BONUS_ISSUE, DAMAGE, EXPIRY, TRANSFER, REVERSAL), pools (SALEABLE/PROMO/QUARANTINE), signed `qty_delta`, unit/value deltas, source traceability, transaction group, idempotency key, business date.
- **Derived balances**: `StockBalance` per branch+medicine+batch with non-negative check constraints; updated only by the posting service.
- **Posting service** (`apps.inventory.services.post_transactions`): atomic ledger+cache writes, deterministic row locking (`select_for_update`, sorted by medicine/batch), negative-stock rejection (`INSUFFICIENT_STOCK`), idempotent replay, batch cache/depletion sync, `ledger_quantities` reconciliation helper.
- **Data migration**: existing batch on-hand quantities backfilled as OPENING transactions + balance cache rows.
- **Batch creation refactor**: catalog batch create now posts through the inventory service (no direct quantity writes); quantity/cost edits on batches are blocked with guidance to use inventory transactions.
- **APIs**: ledger list/detail (filters + date range + search), balances, stock summary, low-stock / near-expiry / expired reports, integrity (cache vs ledger).
- **Reconciliation command**: `check_stock_integrity [--repair]` compares balances and batch caches with ledger sums.
- **Dashboard KPIs**: `stock_value`, `low_stock_count`, `near_expiry_count` now computed from inventory (sales/collection/due remain for later sprints).
- **Frontend**: new `/inventory` page with Stock (summary + low-stock filter), Ledger (type/search filters + pagination), Alerts (low stock, near expiry ≤90d, expired); nav updated (desktop + mobile).

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Inventory smoke script (15 checks) | ✅ 15/15 |
| Negative stock rejected under service validation | ✅ `INSUFFICIENT_STOCK` |
| Idempotent replay returns original posting, no duplicate ledger rows | ✅ |
| Ledger ↔ balance equality after mixed movements | ✅ |
| Batch auto-`DEPLETED` at zero | ✅ |
| Near-expiry (28d) and expired reports | ✅ |
| `check_stock_integrity` | ✅ balances and batch caches match ledger |
| Live HTTP: summary, ledger, integrity, dashboard KPIs | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (11 routes) | ✅ |

### Key endpoints
- `GET /api/v1/inventory/transactions/` (filters: branch, medicine, batch, entry_type, pool, date_from/date_to)
- `GET /api/v1/inventory/balances/`
- `GET /api/v1/inventory/summary/`
- `GET /api/v1/inventory/reports/low-stock|near-expiry|expired/`
- `GET /api/v1/inventory/integrity/`

### Key screens
- `/inventory` (Stock / Ledger / Alerts), dashboard inventory KPIs

### Migrations
- `inventory.0001_initial`, `inventory.0002_backfill_opening_transactions`

### Known limitations
- Idempotency keys apply to single-line postings; multi-line callers use `transaction_group_id` (purchases/sales will follow this).
- Adjustments API/UI (manual corrections, damage/expiry posting) land in Sprint 7; the ledger types and service support them already.
- Transfer entry type is defined but inter-branch transfers remain Phase 2.
- Automated tests deferred per project decision.

### Next
Sprint 4 — Supplier & purchase management: suppliers + ledger, purchases with batch receipt, bonus quantities, discounts, supplier payments/allocation, payable aging, effective cost, atomic purchase confirmation, purchase returns.

---

## Sprint — Supplier & purchase management

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Document numbering** (`apps.common.numbering`): gapless per-branch, per-fiscal-year `DocumentSequence` with row locking (`PUR/PPV/DBN/INV/RCP/CRN/ADJ` prefixes, July–June FY).
- **Accounting foundation**: `FinancialAccount` (CASH/BANK/MFS, branch-scoped, optional negative) and append-only `FinancialTransaction` ledger with balance cache, insufficient-funds guard; default cash account per branch created by `seed_rbac`.
- **Suppliers**: CRUD, payable ledger (append-only, running balance, date filters), payable summary report, `balance_cache` reconciled from ledger.
- **Purchases**: draft with line items (batch number, mfg/expiry, qty, bonus qty, unit cost, line discount, VAT), server-computed totals, effective unit cost with bonus allocation (e.g., 100+10 @ 1.20 → 1.0909), atomic confirmation:
  batch create/merge → purchase + bonus stock postings → supplier payable → optional payment at entry → gapless number.
- **Duplicate supplier invoice control**: blocked with `DUPLICATE_SUPPLIER_INVOICE`, explicit override + reason.
- **Supplier payments**: record with FIFO or manual allocation, partial payments, unallocated advance, account posting, reversal with purchase-status recompute; idempotency keys.
- **Purchase returns**: draft from purchase lines (returnable = qty + bonus − returned), debit note with proportional VAT reversal, stock decrease, payable decrease (excess becomes supplier advance), purchase return status recompute.
- **Purchase cancellation**: only confirmed+unpaid+unreturned and only when stock is unconsumed; full reversal (stock, payable).
- **Payable aging report**: current / 1–30 / 31–60 / 61–90 / 90+ per supplier.
- **Frontend**: `/suppliers` (list, create, ledger panel) and `/purchases` (multi-line purchase form, confirm-with-payment panel, pay panel, return panel, register with status badges); nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Purchase smoke script (17 checks) | ✅ 17/17 |
| Draft totals (bonus → effective cost 1.0909, VAT, round-off) | ✅ |
| Atomic confirm + partial payment at entry | ✅ `PARTIALLY_PAID`, paid 50.00 |
| Idempotent reconfirm returns same purchase | ✅ |
| Stock: purchase + bonus = 110 on hand; bonus ledger entry | ✅ |
| Supplier ledger balance 88.00 and payable aging 88.00 | ✅ |
| Duplicate invoice blocked (409) then override confirmed | ✅ |
| FIFO payment allocation across purchases | ✅ |
| Purchase return: grand 7.00, stock 110 → 105, debit note `DBN-…` | ✅ |
| Confirmed purchase cancel reverses stock to 0 | ✅ |
| Account cache equals account ledger | ✅ |
| `check_stock_integrity` after full flow | ✅ ledger consistent |
| Live HTTP: suppliers, purchases, payable aging, accounts, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (13 routes) | ✅ |

### Key endpoints
- `GET/POST /api/v1/suppliers/`, `GET /api/v1/suppliers/{id}/ledger/`, `GET /api/v1/suppliers/reports/payables/`
- `GET/POST /api/v1/purchases/`, `POST /api/v1/purchases/{id}/confirm/`, `POST /api/v1/purchases/{id}/cancel/`
- `GET/POST /api/v1/supplier-payments/`, `POST /api/v1/supplier-payments/{id}/reverse/`
- `GET/POST /api/v1/purchase-returns/`, `POST /api/v1/purchase-returns/{id}/confirm/`
- `GET /api/v1/purchases/reports/payable-aging/`, `GET /api/v1/accounts/`

### Key screens
- `/suppliers` (register + ledger), `/purchases` (create, confirm/pay, return, register)

### Migrations
- `common.0001_initial`, `accounting.0001_initial`, `suppliers.0001_initial`, `purchases.0001_initial`, `purchases.0002_initial`

### Known limitations
- Cheque lifecycle (pending/cleared/bounced) is recorded as a method only; sub-states arrive with payments hardening.
- Purchase returns reverse cost at the batch's current cost while supplier value uses the purchase's base unit cost — intentional, documented in the service.
- Draft purchase editing replaces all lines (acceptable for MVP).
- Cash accounts start at zero; deposits/withdrawals UI arrives with the finance sprint (service exists).
- Automated tests deferred per project decision.

### Next
Sprint 5 — Customers & sales: customer CRUD + ledger, sales invoices with FEFO batch selection, stock deduction, credit control, due creation, invoice numbering, A4-printable invoice, overselling prevention.

---

## Sprint — Customers & sales invoices

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Customers**: CRUD, types, price tiers (retail/wholesale/custom with per-tier medicine prices), default discount, credit limit/days, credit hold, append-only receivable ledger with running balance, `balance_cache` reconciled from ledger.
- **Tier pricing**: `resolve_unit_price` per customer tier; medicine model extended with retail/wholesale/custom price fields (migration catalog.0005).
- **Sales invoices**: multi-line drafts with auto price resolution, line discounts, VAT, free-goods lines, round-off; draft edit replaces lines.
- **FEFO confirmation** (atomic): saleable batches selected earliest-expiry-first, expired/exhausted excluded, line split into one item per batch with proportional discount/VAT; stock posted via the inventory ledger; `INSUFFICIENT_STOCK` blocks overselling.
- **Numbering**: gapless `INV-{BRANCH}-{FY}-{seq}` inside the transaction.
- **Receivable posting**: customer ledger INVOICE entry with due date = business date + credit days.
- **Credit control**: credit hold blocks sales (`CUSTOMER_ON_HOLD`); credit limit exceeded blocks with `CREDIT_LIMIT_EXCEEDED` unless `SALE_OVERRIDE_CREDIT` override with reason (audited on the invoice).
- **Receipts** (minimum for payment-at-entry): `Payment` + allocations, account posting (`SALE_RECEIPT`), customer ledger `PAYMENT`, FIFO across open invoices, partial/advance, reversal with invoice status recompute. Sprint 6 extends with due-collection UX and aging workflows.
- **Cancellation**: unpaid confirmed invoices can be cancelled with full stock restock and ledger reversal.
- **Receivable aging report**: current / 1–30 / 31–60 / 61–90 / 90+ per customer.
- **Dashboard**: sales_today, collections_today, customer_due, supplier_payable now computed from real data.
- **Frontend**: `/customers` (register + ledger), `/sales` (invoice builder, confirm-with-receipt + credit override, receive payment, register), `/sales/[id]` printable A4 invoice (print CSS), nav reorganised around daily ops.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Sales smoke script (21 checks) | ✅ 21/21 |
| FEFO: 8 units → 5 from earlier batch + 3 from next; zero-row batch handled | ✅ |
| Invoice number `INV-MAIN-26-…` + due date +30d | ✅ |
| Oversell blocked (409) and expired-only stock blocked | ✅ |
| Payment at entry → `PARTIALLY_PAID`, cash +2.00 | ✅ |
| Customer ledger balance = open invoices; FIFO receipt; reversal restores | ✅ |
| Credit limit blocked → override confirmed (audited) | ✅ |
| Cancel restores stock 6 → 10 | ✅ |
| Receivable aging totals match ledger | ✅ |
| `check_stock_integrity` after sales flows | ✅ consistent |
| Live HTTP: dashboard KPIs (sales 46.0, collections 2.0, due 44.0), invoice detail, aging, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (15 routes) | ✅ |

### Key endpoints
- `GET/POST /api/v1/customers/`, `GET /api/v1/customers/{id}/ledger/`
- `GET/POST /api/v1/sales/`, `POST /api/v1/sales/{id}/confirm/`, `POST /api/v1/sales/{id}/cancel/`, `GET /api/v1/sales/fefo/`
- `GET/POST /api/v1/payments/`, `POST /api/v1/payments/{id}/reverse/`
- `GET /api/v1/sales/reports/receivable-aging/`

### Key screens
- `/customers` (register + ledger), `/sales` (builder + confirm/receipt), `/sales/[id]` (printable invoice)

### Migrations
- `sales.0001_initial`, `payments.0001_initial`, `payments.0002_initial`, `catalog.0005_medicine_price_tiers`

### Known limitations
- Sales returns/credit notes (Sprint 7); due-list collection UX and past-due blocking (Sprint 6).
- Manual FEFO batch override (permission `INV_OVERRIDE_FEFO`) not exposed in APIs yet.
- Receipt printing is a screen document (A4 print CSS), no server-side PDF generator yet.
- One final invoice line per batch by design; UI shows the split after confirmation.
- Automated tests deferred per project decision.

### Next
Sprint 6 — Customer payments & due management: due list/aging workflows, collect old dues (FIFO/manual allocation UI), advance handling, collector attribution, daily collection summary, receipt print/share, past-due credit blocking.

---

## Sprint — Customer payments & due management

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Collector attribution**: `Payment.collector` (defaults to the acting user), exposed on receipts and grouped reports.
- **Past-due credit blocking**: confirmation blocks customers with invoices overdue beyond `CUSTOMER_OVERDUE_BLOCK_DAYS` (default 30, configurable) with `CUSTOMER_PAST_DUE`; `SALE_OVERRIDE_CREDIT` override (audited on the invoice) lifts the block.
- **Due list API** `GET /sales/due-list/`: open confirmed invoices with aging buckets (current/1–30/31–60/61–90/90+), days overdue, customer contact, filters (customer, branch, search, `overdue_only`, `min_overdue_days`), totals (outstanding, overdue).
- **Advances**: unallocated receipts remain on account; `GET /customers/reports/advances/` lists customers holding advances with totals; customer `balance_cache` reflects the credit.
- **Daily collection report** `GET /payments/reports/daily-collection/`: totals by method and by collector for a date, branch-scoped.
- **Manual + FIFO allocation** exercised end-to-end: multi-invoice FIFO receipts, explicit allocation to a chosen invoice, partial/advance portions.
- **Frontend**: `/dues` collection desk (summary KPIs, aging table/cards, per-customer collect panel with FIFO-prefilled editable allocations, advance portion indicator, advances card), `/payments` register (daily summary chips, filters, reversal panel, receipt links), `/payments/[id]` printable A4 money receipt, nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Payments smoke script (11 checks) | ✅ 11/11 |
| Due list buckets + totals (35.00 across 2 invoices, current) | ✅ |
| FIFO across invoices: oldest paid, next partial 5.00 | ✅ |
| Overpayment → advance 5.00; customer balance −5.00; advances report | ✅ |
| Manual allocation to a specific invoice | ✅ |
| Past-due (>30d) blocks new sale (409), override confirms | ✅ |
| Daily collection grouped by method + collector | ✅ |
| Receipt reversal restores invoice to UNPAID | ✅ |
| Live: due list (7 invoices, overdue 5.00), daily total 24.00, receipt detail with collector, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (17 routes), `check_stock_integrity` | ✅ |

### Key endpoints
- `GET /api/v1/sales/due-list/`
- `GET /api/v1/customers/reports/advances/`
- `GET /api/v1/payments/reports/daily-collection/`
- `GET/POST /api/v1/payments/`, `POST /api/v1/payments/{id}/reverse/`

### Key screens
- `/dues` (collection desk + advances), `/payments` (register + daily summary), `/payments/[id]` (printable receipt)

### Migrations
- `payments.0003_payment_collector`

### Known limitations
- Cheque lifecycle sub-states still pending (recorded as method + reference).
- Advance auto-application at sale confirmation is manual for now (advances are applied explicitly through allocation when collecting).
- Receipt print is browser-based A4 (no server-side PDF generator yet).
- Automated tests deferred per project decision.

### Next
Sprint 7 — Returns, expired stock, damage & adjustments: sales returns with restock/quarantine, credit notes and refund methods, purchase return UI, stock adjustments (damage/expiry/loss) with approvals, reason tracking, audit, financial impact.





