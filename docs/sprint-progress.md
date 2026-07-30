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

---

## Sprint — Returns, expired stock, damage & adjustments

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Sales returns**: draft from a confirmed invoice (qty ≤ sold − returned), per-line condition (`RESELLABLE / DAMAGED / EXPIRED`), gapless credit note `CRN-…`; proportional discount/VAT reversal at the original line values.
  - Resellable + non-expired → restocked to the original batch (saleable pool, `SALES_RETURN` movement); damaged/expired → **quarantine pool** (never saleable).
  - Customer ledger `SALES_RETURN` credit; refund methods: customer credit / adjust dues (ledger credit), cash/bank (ledger credit settled via `ADVANCE_REFUND` + `REFUND` account transaction, `RETURN_REFUND` permission).
  - Invoice `return_status` recomputes to `PARTIALLY_RETURNED / FULLY_RETURNED`.
- **Purchase returns UI**: returns now listed in the unified Returns page (create/confirm already existed from Sprint 4).
- **Stock adjustments**: `StockAdjustment` + items with direction (increase/decrease), pools (`SALEABLE/PROMO/QUARANTINE`), optional pool **move** (e.g., saleable → quarantine), reason codes (damage, expiry write-off, count variance, found stock, promo replenish, recall disposal), value computed at batch cost.
  - Below the configurable threshold (`STOCK_ADJUSTMENT_APPROVAL_THRESHOLD`, default 5,000) → posted immediately with `ADJ-…` number; above → `PENDING_APPROVAL` requiring a **different user** to approve (dual control, `SELF_APPROVAL_NOT_ALLOWED`), with reject flow.
  - Reversal via compensating movements; statuses `POSTED/REJECTED/REVERSED` with actor audit fields.
  - DEPLETED batches revive automatically when restocked (inventory service).
- **Critical RBAC fix**: module wildcards (`inventory:*`, `sale:*`, …) never resolved because permission codes carry no module prefix — roles effectively had missing permissions, masked until now by Owner-superuser tests. Resolver now maps modules to their catalog codes; re-seeded roles (Warehouse 17, Sales Operator 12, Accountant 29 permissions).
- **Frontend**: `/returns` (sales + purchase return registers), `/adjustments` (create form with batch picker, approve/reject/reverse, approval queue), sales register **Return** panel (item/condition/reason/refund method), nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Returns & adjustments smoke script (15 checks) | ✅ 15/15 |
| Resellable return: credit note 7.00, stock 40→43, invoice PARTIALLY_RETURNED | ✅ |
| Damaged return → quarantine 2, saleable unchanged | ✅ |
| Over-return blocked (409); final return → FULLY_RETURNED | ✅ |
| Cash refund: account −9.00, ledger credit settled | ✅ |
| Damage adjustment auto-posted below threshold; reversal restores stock | ✅ |
| Quarantine move shifts pools (−2 saleable, +2 quarantine) | ✅ |
| High-value adjustment → PENDING; self-approval 403; different user approves → POSTED | ✅ |
| Live: returns CRN 9.00 with restock flag, ADJ posted by approver, purchase returns, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (19 routes), `check_stock_integrity` | ✅ |

### Key endpoints
- `GET/POST /api/v1/sales-returns/`, `POST /api/v1/sales-returns/{id}/confirm/`
- `GET/POST /api/v1/inventory/adjustments/`, `POST …/{id}/approve|reject|reverse/`

### Key screens
- `/returns` (sales + purchase returns), `/adjustments` (register + approval queue), sales `Return` panel

### Migrations
- `sales.0002` (returns + returned_qty), `sales.0003` (ledger entry type), `inventory.0003` (adjustments), `accounting.0002` (REFUND entry type)

### Known limitations
- Write-off financial impact is recorded in the inventory ledger value (`value_delta`); expense/P&L posting arrives with the finance sprint.
- Confirmed sales returns are not yet reversible (draft can be deleted; compensation via counter-return not yet exposed).
- Adjustment evidence attachments deferred.
- Automated tests deferred per project decision.

### Next
Sprint 8 — Expenses, income & financial accounts: expense/income categories and postings, cash/bank/MFS account management, deposits/withdrawals, transfers, account ledger and balances, reversal flows, dashboard financial KPIs.

---

## Sprint — Expenses, income & financial accounts

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Expense categories & income categories**: seeded defaults (9 expense / 5 income), CRUD-capable APIs.
- **Expenses**: create (branch, category, amount, paying account, payee, reference, note), automatic posting below `EXPENSE_APPROVAL_THRESHOLD` (default 5,000), `PENDING_APPROVAL` above with **dual-control** approval (`SELF_APPROVAL_NOT_ALLOWED`), reject flow, reversal via compensating `EXPENSE_REVERSAL` account entry, gapless `EXP-…` numbering, idempotency keys, insufficient-funds guard inherited from account posting.
- **Other income**: immediate posting to the receiving account with `INC-…` numbering, reversal via `INCOME_REVERSAL`.
- **Account management**: create cash/bank/MFS accounts (branch or company-level), deposit, withdrawal (negative balance blocked unless `allow_negative`), **inter-account transfers as a paired `TRANSFER_OUT/TRANSFER_IN` group** posted atomically, account ledger with running balance, balance cache reconciled from the ledger.
- **Reports**: expense summary by category (posted only), income summary by category; dashboard now includes **cash position** across accounts.
- **Frontend**: `/accounts` (registry, balances, create, ledger + deposit/withdraw/transfer panel), `/expenses` (summary chips, create, approval queue, reject, reverse), `/income` (summary, create, reverse), nav + dashboard KPI updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Finance smoke script (19 checks) | ✅ 19/19 |
| Deposit 10,000 → balance; transfer 2,000 pairs (bank −2,000 / cash +2,000); withdraw 500 | ✅ |
| Insufficient funds blocked (409 `INSUFFICIENT_FUNDS`) | ✅ |
| Below-threshold expense auto-posted; above-threshold pending | ✅ |
| Self-approval blocked (403); accountant approves → POSTED; bank 1,200.00 | ✅ |
| Expense reversal restores account; income posts + reversal | ✅ |
| Account ledger running balance = cache; every account cache = ledger sum | ✅ |
| Expense summary excludes reversed; income summary after reversal | ✅ |
| Live: dashboard cash 110,875.0, accounts, summaries, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (21 routes) | ✅ |

### Key endpoints
- `GET/POST /api/v1/expense-categories|income-categories/`
- `GET/POST /api/v1/expenses/` (+`/{id}/approve|reject|reverse/`, `reports/summary/`)
- `GET/POST /api/v1/incomes/` (+`/{id}/reverse/`, `reports/summary/`)
- `GET/POST /api/v1/accounts/` (+`/{id}/ledger|deposit|withdraw/`, `POST /accounts/transfer/`)

### Key screens
- `/accounts` (ledger & operations), `/expenses` (approval queue), `/income`

### Migrations
- `accounting.0003` (categories, expenses, incomes, entry types), `common.0002` (doc types)

### Known limitations
- Stock write-off/expiry loss P&L linkage still computed from inventory ledger values (profit sprint consolidates this).
- Cheque lifecycle sub-states remain pending.
- Account statement export (PDF/Excel) pending; browser view only.
- Automated tests deferred per project decision.

### Next
Sprint 9 — Profit & financial overview: revenue/COGS/gross profit/net profit, inventory valuation, receivables/payables summary, damage & expiry losses, cash/bank summary, period comparisons — reconciling with ledgers.

---

## Sprint — Profit & financial overview

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Reports app** (`apps.reports`) with three ledger-reconciling endpoints:
  - `GET /api/v1/reports/profit-loss/` — period `date_from/date_to`:
    - Net revenue = confirmed invoice net (subtotal − discount) − confirmed return net (subtotal − discount reversal)
    - COGS from the **inventory ledger**: SALE + SALES_RETURN + sales-cancel REVERSAL movements (batch actual cost)
    - Gross profit + margin %; loss breakdown: damage, expiry, adjustment net, adjustment reversals
    - Posted expenses and other income; net profit
    - **Previous equal-length period** + delta and delta %
    - Reconciliation block (customer ledger movement vs receipts)
  - `GET /api/v1/reports/inventory-valuation/` — per-branch saleable/quarantine/promo quantities and values at batch cost, grand total
  - `GET /api/v1/reports/financial-position/` — receivables, payables, cash & bank (per-account list), saleable/quarantine stock value, net working position
- **Permission gating**: P&L and valuation require `REPORT_VIEW_COST`; position requires `REPORT_VIEW` — verified that a Sales Operator gets 403 on profit and 200 on position.
- **Frontend**: `/reports` with three tabs (Profit & Loss with date range + comparison cards + reconciliation; Inventory valuation by branch; Position with KPI cards and account list), nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Reports smoke script (13 checks) | ✅ 13/13 |
| Net revenue delta 40.00 (50 sale − 10 return) and COGS delta 16.00 (10×2 − 2×2) | ✅ |
| Gross profit delta 24.00; damage loss delta 6.00; expense 200 / income 150 | ✅ |
| Net profit delta −32.00; comparison block present | ✅ |
| Valuation API total equals independent ORM sum (1,728.54) | ✅ |
| Position equals ledger sums (receivables/payables/cash) | ✅ |
| Sales Operator denied P&L (403), allowed position (200) | ✅ |
| Live: P&L month (revenue 122.00, COGS 57.00, gross 65.00, margin 53.28%), valuation, position, frontend | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build`, `check_stock_integrity` | ✅ |

### Key endpoints
- `GET /api/v1/reports/profit-loss/`
- `GET /api/v1/reports/inventory-valuation/`
- `GET /api/v1/reports/financial-position/`

### Key screens
- `/reports` (P&L + valuation + position tabs)

### Migrations
- none (read-only reporting layer; no schema changes)

### Known limitations
- P&L is period/movement based: a sales cancellation reversing into a later period affects that later period's COGS (documented, acceptable for MVP).
- No export (PDF/Excel) yet for reports (browser view).
- Cancelled invoice revenue/COGS offset only when the reversal movement falls in the selected period.
- Automated tests deferred per project decision.

### Next
Sprint 10 — Doctors & representatives: doctor CRUD, doctor–medicine mapping, territories, representatives, assignments, doctor visits with samples from promotional stock, visit coverage and activity reports, doctor-wise and rep-wise sales attribution.

---

## Sprint — Doctors & representatives

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Representatives app** (`apps.representatives`):
  - Territories (region → area → territory hierarchy, unique per parent)
  - Representatives (sales/medical, branch, optional user link, reports-to)
  - Effective-dated assignments (customer/doctor/territory) with a single open row per pair (partial unique constraint); `assign` closes the previous open row in the same transaction; deactivation guard blocks reps with open assignments
- **Doctors app** (`apps.doctors`):
  - Doctor master (specialty, degrees, BMDC registration unique, category A/B/C, doctor type, territory, consent note)
  - Doctor chambers (model), **effective-dated doctor–medicine mappings** (one open mapping per pair), mapping priority/notes
  - **Doctor visits**: planned / completed / missed lifecycle, products discussed, outcome, next visit date, notes; **samples issued from the promotional stock pool** via the inventory posting service (`BONUS_ISSUE`), linked to the resulting ledger transaction; insufficient promo stock blocks completion
  - Visit coverage report (per rep: planned/completed/missed/cancelled + coverage %, ad-hoc completed count)
- **Sales attribution**: `SalesInvoice.doctor` and `SalesInvoice.sales_rep` fields; sales-by-doctor and sales-by-rep report endpoints with an "Unassigned" bucket; attribution names returned on invoice read/write.
- **RBAC**: Branch Manager granted `REP_MANAGE` and `TERRITORY_MANAGE`; roles re-seeded.
- **Frontend**: `/doctors` (directory, mappings, visit logging with promo samples, visit history), `/reps` (representatives + assignments + territories), Reports tabs "Sales by doctor" / "Sales by rep", nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| CRM smoke script (12 checks) | ✅ 12/12 |
| Territory/rep/doctor setup, mapping, doctor→MR and customer→SR assignments | ✅ |
| Visit completed with promo sample: promo balance 20 → 18, sample linked | ✅ |
| Insufficient promo stock blocked (409 `INSUFFICIENT_STOCK`) | ✅ |
| Missed visit + coverage (2 planned, 1 completed, 1 missed, 50%) | ✅ |
| Attributed invoice (doctor + sales rep names); sales-by-doctor 20.00, sales-by-rep 20.00; Unassigned bucket | ✅ |
| Live: doctors, reps, coverage, attribution, frontend routes | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (23 routes), `check_stock_integrity` | ✅ |

### Key endpoints
- `GET/POST /api/v1/doctors/` (+`/{id}/medicines/`), `POST /api/v1/doctor-medicines/{id}/end/`
- `GET/POST /api/v1/doctor-visits/` (+`/{id}/complete/`, `/{id}/miss/`), `GET /api/v1/doctors/reports/visit-coverage/`
- `GET/POST /api/v1/representatives/` (+`/{id}/assign|unassign/`, `/{id}/assignments/`), `GET/POST /api/v1/territories/`
- `GET /api/v1/reports/sales-by-doctor|sales-by-rep/`

### Key screens
- `/doctors` (mappings + visits + samples), `/reps` (assignments + territories), `/reports` (attribution tabs)

### Migrations
- `representatives.0001`, `doctors.0001/0002`, `sales.0004` (attribution fields)

### Known limitations
- Doctor chambers and rep targets/commissions are modeled/planned but not exposed in this sprint's UI (targets remain Phase 2 per open questions).
- Visit edit window (24h) not yet enforced; edits are audited by default model timestamps only.
- GPS/photo visit evidence deferred to Phase 2.
- Automated tests deferred per project decision.

### Next
Sprint 11 — Dashboard & reports completion: expand dashboard KPIs (sales trend, top items, low stock, near expiry alerts), add report exports, complete the report catalog (sales/purchase/stock/expiry/receivable/payable/expense/profit/doctor/rep activity) with date filtering, search, pagination and permission gating.

---

## Sprint — Dashboard widgets & report catalog completion

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Dashboard widgets** (`GET /dashboard/widgets/`): last-N-days sales trend (per-day revenue + invoice counts), top 5 items by revenue, top 5 customers, low-stock preview (worst 5 below reorder level), near-expiry preview (next 5 batches ≤ 90 days) — all branch-scoped.
- **Report catalog additions** (all with `date_from/date_to`, search, CSV export):
  - `GET /reports/sales-summary/` — daily invoice count, net revenue, VAT, grand totals + period totals
  - `GET /reports/purchases-summary/` — daily confirmed purchase counts, net cost, VAT, grand totals
  - `GET /reports/sales-by-item/` — quantity, gross, discount, net per medicine; **cost and gross profit only with `REPORT_VIEW_COST`** (masked otherwise, including CSV columns)
  - `GET /reports/sales-by-customer/` — invoices, net revenue, paid, outstanding per customer
- **CSV export** (`?export=csv`) with `text/csv` content type and attachment filename for all four new endpoints; report styling honors permission masking.
- **Dashboard UI**: sales-trend bar chart, top items/customers lists, low-stock and near-expiry alert cards with links to inventory; operations KPI values formatted as money.
- **Reports UI**: new tabs Sales summary (sales + purchases cards with CSV buttons), Sales by item (cost columns conditional on permission), Sales by customer, Purchases; CSV downloads through an authenticated `apiDownload` helper.
- **Fix discovered**: Django 6.1.1 mis-resolves multiple aggregate expressions in one `annotate()` (mixing plain `Sum('field')` with expression sums raises `FieldError`). New report endpoints aggregate in Python over `values()` rows — deterministic and independently verified against ORM sums.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Reports/widgets smoke script (11 checks) | ✅ 11/11 |
| Widgets: trend, top items, low stock, near expiry structure | ✅ |
| Sales summary totals equal all-time ORM (184.00) | ✅ |
| Purchases summary totals equal ORM (131.00) | ✅ |
| Sales-by-item qty equals ORM (10.000 for SALEPL1) | ✅ |
| CSV export: header + row count match | ✅ |
| Owner sees cost/profit; Sales Operator sees values without cost, CSV omits cost column | ✅ |
| Live: CSV `text/csv` + attachment header; dashboard/reports routes 200 | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (23 routes), `check_stock_integrity` | ✅ |

### Key endpoints
- `GET /api/v1/dashboard/widgets/`
- `GET /api/v1/reports/sales-summary|purchases-summary|sales-by-item|sales-by-customer/` (all `?export=csv`)

### Key screens
- Dashboard widgets section; `/reports` tabs (Sales summary, Sales by item, Sales by customer, Purchases + existing tabs)

### Migrations
- none

### Known limitations
- Reports aggregate in Python for correctness; at very large volumes (>100k rows/period) async generation will be introduced with exports.
- Expiry/receivable/payable/expense/income reports remain on their module pages (inventory alerts, dues, payables, expense/income summaries) rather than duplicated in the catalog.
- Automated tests deferred per project decision.

### Next
Sprint 12 — Security, audit, migration & go-live: audit log review UI, security hardening (rate limits, headers, production settings), health/monitoring, backup & restore procedures, opening-data import tooling (medicines, stock, dues, payables, balances, users), reconciliation, UAT checklist and go-live readiness.

---

## Sprint — Security, audit, migration & go-live

**Status:** ✅ Complete (verified end-to-end) — **12/12 sprints delivered**

### Implemented
- **Audit API + UI**: `GET /api/v1/audit-logs/` with filters (entity type/id, action, actor, request id, date range, branch), branch-scoped, `AUDIT_VIEW` gated; `/audit` page with filters, pagination and before/after JSON diff viewer.
- **Security hardening**:
  - Redis cache backend (db 6) and DRF throttling: user 3000/h, anon 120/h, login scope 20/min (verified 429 after rapid attempts); auth view uses `ScopedRateThrottle`.
  - Security headers (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`), CSRF trusted origins env-driven, HSTS + SSL redirect automatically enforced when `DEBUG=False`, refresh cookie `Secure` by default in production.
- **Backup & restore commands**: `backup_db` (pg_dump custom format, real dump verified), `restore_db --confirm` (pg_restore clean restore), plus `check_ledger_integrity` (customer/supplier/account cache reconciliation with `--repair`).
- **Opening-data import tooling** (CSV, `--dry-run`, validation report, idempotent, `OPENING` ledger entries only):
  - `import_medicines`, `import_users`, `import_opening_stock`, `import_opening_balances`, `import_opening_accounts`
  - Templates in `docs/import-templates/`
  - Fixed a real bug: `--dry-run` was creating batches before validation.
- **Operations & go-live documentation**: `docs/operations.md` (health, backup/restore, imports, user provisioning, incidents, deploy/rollback, patching) and `docs/go-live-checklist.md` (freeze, data prep, staging dry run, cutover order, hypercare, rollback triggers).
- **Environment recovery**: Postgres.app's trust-auth permission helper crashed repeatedly (`Postgres.app failed to verify "trust" authentication`). Restarted and then moved dev to the existing Homebrew PostgreSQL 17 cluster on port 5433 (`pg_ctl -D /opt/homebrew/var/postgresql@17 -o "-p 5433" start`), migrated + re-seeded; `.env`/`.env.example`/README updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Sprint 12 smoke script (13 checks) | ✅ 13/13 |
| Audit API lists login events; entity filter; 401 without token | ✅ |
| `check_ledger_integrity` clean; `check_stock_integrity` clean | ✅ |
| Login throttle returns 429; login works after window reset | ✅ |
| `backup_db` produces a non-empty custom-format dump | ✅ |
| Import commands: dry-run validates, real import idempotent (re-run skips) | ✅ |
| Live: audit API (11 events), starter demo data, deep health (db/redis ok, worker idle), frontend `/audit` + dashboard 200 | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build` (24 routes) | ✅ |

### Key endpoints
- `GET /api/v1/audit-logs/` (filters + pagination)
- Commands: `backup_db`, `restore_db`, `check_ledger_integrity`, `check_stock_integrity`, `import_medicines|users|opening_stock|opening_balances|opening_accounts`

### Key screens
- `/audit` (event log with before/after diffs)

### Migrations
- none

### Known limitations
- Celery worker must be running for deep-health `celery: ok` and background jobs; run `celery -A config worker --pool=threads` on macOS dev.
- Gunicorn/Nginx production compose is provided, but TLS/CDN/S3 credentials are deployment-specific and documented, not preconfigured.
- UAT execution is a business activity; the checklist and all verification scripts are prepared.
- Automated tests remain deferred per the project decision made at the start.

---

## Program Summary

All 12 sprints are complete: foundation/auth/RBAC, catalog & batches, inventory ledger, purchasing, sales & FEFO, collections & dues, returns & adjustments, finance, profit reporting, doctors & representatives, dashboard & report catalog, and security/audit/migration/go-live. The system currently runs end-to-end (Django + DRF + PostgreSQL + Redis + Celery worker/beat, Next.js + TanStack Query) with 24 frontend routes, append-only ledgers for stock/customer/supplier/accounts, batch-actual costing, dual-control approvals, per-branch isolation, audit logging, and CSV export.

---

## Sprint 13 — Completeness pass: wiring & fixes

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Port standardised on 8000** for the dev API (frontend env, README, backend `runserver 8000`).
- **Sales attribution UI**: doctor and sales-rep selectors on the invoice form — hand-entered sales now feed the doctor/rep reports instead of "Unassigned".
- **FEFO override**: per-line batch picker on the invoice form (permission `INV_OVERRIDE_FEFO`, audited `fefo_override` + reason on the invoice); backend validates batch branch/medicine/active/not-expired and blocks users without the permission.
- **Default customer discount**: `default_discount_pct` is now applied when a line discount is omitted (was a dead field).
- **Delivery tracking**: `POST /sales/{id}/mark-delivered/` (idempotent) + "Mark delivered" button + Delivered badge; `delivered_at/delivered_by` recorded.
- **Purchase cancel UI**: Cancel button + reason panel for confirmed, unpaid, unreturned purchases (backend rules enforced).
- **Edit + deactivate UI** for customers (incl. credit hold toggle + reason, default discount), suppliers, and branches; customer/supplier/branch status toggles.
- **Audit CSV export**: `GET /audit-logs/export/` (requires `AUDIT_EXPORT`) + Export button on the audit page with current filters.
- **Frontend idempotency keys**: confirm, receipt, sales-return, cancel and payment POSTs now send `Idempotency-Key` (generated per panel open) — double-tap/retry safe.
- **Advance auto-apply**: `AUTO_APPLY_ADVANCE` setting; when enabled, customer credit is applied to new invoices at confirmation (`ADVANCE_APPLIED` ledger entry, paid status recomputed) using the pre-invoice balance (fixed ordering bug found in smoke).

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Sprint 13 smoke script (11 checks) | ✅ 11/11 |
| Default discount (10%) applied: discount 2.00, grand 21.00 | ✅ |
| FEFO auto picks earliest batch; override to later batch with reason recorded | ✅ |
| Operator without `INV_OVERRIDE_FEFO` blocked (403) | ✅ |
| Mark-delivered idempotent; advance auto-apply posts 5.00 paid on a 12.00 invoice | ✅ |
| Audit CSV export (200 + header) and 403 without `AUDIT_EXPORT` | ✅ |
| Live on port 8000: login, audit export, all pages 200 (after clean rebuild) | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build`, stock & ledger integrity | ✅ |

### Key endpoints
- `POST /api/v1/sales/{id}/mark-delivered/`
- `GET /api/v1/audit-logs/export/`

### Migrations
- `sales.0005` (fefo_override, fefo_override_reason, delivered_at, delivered_by)

### Known limitations
- Frontend idempotency keys cover confirm/receipt/return/cancel; purchase payments still use plain POST (keyed service-side only).
- The user's dev server needed a `npm run dev` restart after the env port change; a stale `.next` caused transient 500s, resolved by a clean `next build`.
- Remaining Tier 2/3 gaps (settings module, fiscal period locking, notifications, attachments, PWA, global search, branch switcher, pack units, cheque lifecycle, statement exports) are scheduled next.

---

## Sprint 14 — Settings module & fiscal period locking

**Status:** ✅ Complete (verified end-to-end)

### Implemented
- **Settings module**:
  - `Setting` model (company scope + branch overrides, JSON values) and service with defaults; `GET/PUT /api/v1/settings/` (grouped by company / approvals / credit / expiry / features / numbering), unknown keys rejected, `SETTINGS_VIEW/MANAGE` gated.
  - Live wiring: expense & stock-adjustment approval thresholds, customer overdue-block days, `AUTO_APPLY_ADVANCE`, and **document numbering prefixes/width** are read from settings with env fallbacks (verified: threshold 100 made a 200-value adjustment require approval; `PURCHASE_PREFIX=TSTP` produced `TSTP-…` numbers on a new branch).
- **Fiscal period locking**:
  - `FiscalPeriod` model (July–June fiscal months) + services; periods auto-created for the current and next fiscal year by `seed_rbac`.
  - `ensure_period_open()` enforced centrally in all four posting choke-points (inventory `post_transactions`, account `post_account_transaction`, supplier ledger, customer ledger) — which covers sales, purchases, payments, returns, adjustments, expenses/incomes, account operations and reversals.
  - `GET/POST /api/v1/periods/` with lock/unlock actions; lock returns a close checklist (pending expenses/adjustments); only `PERIOD_LOCK` holders can lock, unlock requires `PERIOD_OVERRIDE`; locked months raise `PERIOD_LOCKED` (409).
- **Settings UI**: `/settings` page with tabs (Company, Approvals, Credit & Expiry, Features, Numbering, Fiscal periods incl. lock/unlock with reason), nav updated.

### Verification (manual, no automated tests per project decision)
| Check | Result |
|---|---|
| Sprint 14 smoke script (13 checks) | ✅ 13/13 |
| Settings round-trip + unknown-key rejection | ✅ |
| Live threshold (200 > 100 → PENDING); numbering prefix from settings on new branch | ✅ |
| Period lock → operator posting blocked `PERIOD_LOCKED`; owner override allowed; unlock restores; operator cannot unlock | ✅ |
| Live: settings groups, 24 periods (2 FYs), settings page 200 | ✅ |
| `manage.py check`, `makemigrations --check`, `ruff`, `next build`, stock & ledger integrity | ✅ |

### Key endpoints
- `GET/PUT /api/v1/settings/`
- `GET /api/v1/periods/`, `POST /api/v1/periods/{id}/lock|unlock/`

### Key screens
- `/settings` (6 tabs incl. fiscal period lock/unlock)

### Migrations
- `common.0003` (Setting, FiscalPeriod)

### Known limitations
- Reversal posting uses today's date, so reversing into a locked month is blocked like any posting (override available).
- Numbering prefix changes apply to new sequences (new fiscal year/branch); existing documents keep their numbers.
- Tier 3 items remain (PWA, global search, branch switcher, pack units, cheque lifecycle, exports).











