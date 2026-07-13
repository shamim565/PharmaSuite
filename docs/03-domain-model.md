# Phase 3 — Domain & Data Design

**Document ID:** DOC-DOM-001
**Version:** 1.0 (Phase 3 baseline)
**Status:** Complete — pending Batch B review
**Parent:** `docs/01-requirements-specification.md`, `docs/02-system-analysis.md`
**Related:** `docs/03-domain/ledgers-costing-integrity.md`, `docs/03-domain/entities-*.md`, `docs/04-erd.md`

---

## Phase 3 Header (required format)

**Objective.** Define the domain model — bounded modules, entities, fields, constraints, relationships, ledgers, costing and integrity/concurrency rules — before any technical architecture or API design.

**Expected deliverables.**
1. Bounded module map and entity index — this document
2. Entity catalog with fields/types/constraints — `docs/03-domain/entities-01…04`
3. Ledger, costing, and database integrity/concurrency design — `docs/03-domain/ledgers-costing-integrity.md`
4. Text ERD — `docs/04-erd.md`

**Decisions inherited.** DEC-001…010, A-001…040, BR-* (98 rules), UC-* (95 use cases), edge cases EC-001…045.

**Unresolved business decisions.** Open questions Q-013/Q-011 (reservation) and Q-029 (cheque) affect entity states only; defaults designed in. Q-016 (stock counting) affects only a future `StockCount` pair of entities — deferred to Phase 2 backlog.

**Assumptions.** Two entity-level assumptions added (A-041, A-042) — see footer.

---

## 1. Bounded Modules

The domain is partitioned into 12 modules. A module owns its entities exclusively; other modules interact only through service interfaces (Phase 4) — never by writing another module's tables.

| # | Module | Responsibility | Owns entities | Depends on (read-only/services) |
|---|---|---|---|---|
| 1 | **Identity & Access** | Users, roles, permissions, sessions, branch membership | User, Role, Permission, RolePermission, UserRole, UserBranch, Session, LoginAttempt, PasswordHistory | Branch |
| 2 | **Branch** | Branch master, branch settings, branch lifecycle | Branch, Setting (branch-scoped rows) | — |
| 3 | **Catalog** | Medicines, generics, manufacturers, categories, units/conversions, barcodes, price tiers | Medicine, Generic, Manufacturer, MedicineCategory, Unit, MedicineUnitConversion, MedicineBarcode | Branch (settings) |
| 4 | **Inventory** | Batches, stock ledger, balances, adjustments, sequences | MedicineBatch, InventoryTransaction, StockBalance, StockAdjustment, StockAdjustmentItem, DocumentSequence | Catalog, Branch |
| 5 | **Procurement** | Suppliers, purchases, supplier payments, purchase returns | Supplier, SupplierLedgerEntry, Purchase, PurchaseItem, SupplierPayment, SupplierPaymentAllocation, PurchaseReturn, PurchaseReturnItem | Catalog, Inventory, Finance, Branch |
| 6 | **Sales** | Customers, invoices, sales returns | Customer, CustomerLedgerEntry, SalesInvoice, SalesInvoiceItem, SalesReturn, SalesReturnItem | Catalog, Inventory, CRM (doctor refs), Branch |
| 7 | **Payments** | Customer payments, allocations, advances, cheque lifecycle | Payment, PaymentAllocation | Sales, Finance, Branch |
| 8 | **CRM** | Doctors, mappings, visits, samples, representatives, territories, targets | Doctor, DoctorChamber, DoctorMedicine, DoctorVisit, DoctorVisitSample, Representative, RepresentativeAssignment, Territory, RepresentativeTarget | Catalog, Inventory (promo stock), Branch |
| 9 | **Finance** | Financial accounts, account ledger, expenses, income, fiscal periods, opening balances | FinancialAccount, FinancialTransaction, Expense, ExpenseCategory, Income, IncomeCategory, FiscalPeriod | Branch, Settings |
| 10 | **Reporting** | Query/aggregation layer, report jobs (no owned business entities) | ReportJob | All modules (read-only) |
| 11 | **Platform** | Settings, notifications, audit, attachments, idempotency | Setting, Notification, NotificationTemplate, AuditLog, Attachment, IdempotencyKey | Branch |
| 12 | **Audit** | Immutable event history (shared service, owns AuditLog) | AuditLog | — |

**Dependency direction:** Identity/Branch/Platform are foundational; Catalog depends on Branch; Inventory on Catalog; Procurement/Sales on Inventory + Finance services; Payments on Sales; CRM on Catalog/Inventory; Reporting reads everything. No cycles.

---

## 2. Domain Design Principles

| # | Principle | Consequence |
|---|---|---|
| P-01 | **Ledgers are the source of truth**; balance columns are derived caches updated in the same transaction and rebuildable (DEC-007) | Nightly reconciliation jobs; repair tooling |
| P-02 | **Append-only ledgers**; no UPDATE/DELETE on ledger rows | Reversals via compensating entries |
| P-03 | **Branch isolation** on every operational table via `branch_id` (BR-BRANCH-001) | Query scoping + composite indexes prefixed by `branch_id` |
| P-04 | **Exact decimals only** (A-007): money `NUMERIC(14,2)`, unit price/cost `NUMERIC(14,4)`, qty `NUMERIC(14,3)` | No float anywhere; rounding per BR-DATA-002 |
| P-05 | **UUIDv7 primary keys** on all entities (time-ordered; no ID enumeration; merge-friendly); ledger tables add a monotonic `seq` for ordering | Smaller index contention than UUIDv4; external IDs reveal nothing |
| P-06 | **Soft delete for masters** referenced by history (`deleted_at`); ledgers and documents are never deleted | Historical integrity preserved |
| P-07 | **Audit on every mutation** via the audit service with before/after snapshots (BR-AUD-001) | Shared columns + audit table |
| P-08 | **Optimistic versioning** (`version` integer) on mutable masters to detect lost updates; pessimistic row locks only for money/stock paths | Clear conflict semantics |
| P-09 | **Idempotency at the edge**: `IdempotencyKey` unique per actor+endpoint+key; replays return stored response | Duplicate-safe retries (BR-AUD-004) |
| P-10 | **Status dimensions, not mega-enums** (state-machines doc §1) | Fewer invalid combinations |
| P-11 | **Business dates are local (Asia/Dhaka), timestamps UTC** | `business_date` DATE columns on documents; `created_at` TIMESTAMPTZ |
| P-12 | **Monetary documents store both computed and override metadata** (override reason, actor, permission used) for the Exception Report | Audit/report completeness |

### 2.1 Common columns

Every operational table carries: `id` (UUIDv7 PK), `branch_id` (FK, where applicable), `created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at` (masters only), `version` (masters and mutable documents). Document tables add: `status` dimensions, `number` (nullable until confirm), `business_date`.

### 2.2 Naming conventions
`snake_case` tables (plural), singular entity names in code; FK columns `<entity>_id`; enum values `UPPER_SNAKE`; index names `ix_<table>_<cols>`; constraint names `ck_<table>_<rule>`, `uq_<table>_<cols>`, `fk_<table>_<ref>`.

---

## 3. Entity Index

| DB ID | Entity | Module | File |
|---|---|---|---|
| DB-IAM-001 | User | Identity | entities-01 |
| DB-IAM-002 | Role | Identity | entities-01 |
| DB-IAM-003 | Permission | Identity | entities-01 |
| DB-IAM-004 | RolePermission | Identity | entities-01 |
| DB-IAM-005 | UserRole | Identity | entities-01 |
| DB-IAM-006 | UserBranch | Identity | entities-01 |
| DB-IAM-007 | Session | Identity | entities-01 |
| DB-IAM-008 | LoginAttempt | Identity | entities-01 |
| DB-IAM-009 | PasswordHistory | Identity | entities-01 |
| DB-BRN-001 | Branch | Branch | entities-01 |
| DB-CAT-001 | Medicine | Catalog | entities-01 |
| DB-CAT-002 | Generic | Catalog | entities-01 |
| DB-CAT-003 | Manufacturer | Catalog | entities-01 |
| DB-CAT-004 | MedicineCategory | Catalog | entities-01 |
| DB-CAT-005 | Unit | Catalog | entities-01 |
| DB-CAT-006 | MedicineUnitConversion | Catalog | entities-01 |
| DB-CAT-007 | MedicineBarcode | Catalog | entities-01 |
| DB-INV-001 | MedicineBatch | Inventory | entities-02 |
| DB-INV-002 | InventoryTransaction | Inventory | entities-02 |
| DB-INV-003 | StockBalance | Inventory | entities-02 |
| DB-INV-004 | StockAdjustment | Inventory | entities-02 |
| DB-INV-005 | StockAdjustmentItem | Inventory | entities-02 |
| DB-INV-006 | DocumentSequence | Platform/Inventory | entities-02 |
| DB-PUR-001 | Supplier | Procurement | entities-02 |
| DB-PUR-002 | SupplierLedgerEntry | Procurement | entities-02 |
| DB-PUR-003 | Purchase | Procurement | entities-02 |
| DB-PUR-004 | PurchaseItem | Procurement | entities-02 |
| DB-PUR-005 | SupplierPayment | Procurement | entities-02 |
| DB-PUR-006 | SupplierPaymentAllocation | Procurement | entities-02 |
| DB-PUR-007 | PurchaseReturn | Procurement | entities-02 |
| DB-PUR-008 | PurchaseReturnItem | Procurement | entities-02 |
| DB-SALE-001 | Customer | Sales | entities-03 |
| DB-SALE-002 | CustomerLedgerEntry | Sales | entities-03 |
| DB-SALE-003 | SalesInvoice | Sales | entities-03 |
| DB-SALE-004 | SalesInvoiceItem | Sales | entities-03 |
| DB-SALE-005 | Payment | Payments | entities-03 |
| DB-SALE-009 | PaymentMethodLine | Payments | entities-03 |
| DB-SALE-006 | PaymentAllocation | Payments | entities-03 |
| DB-SALE-007 | SalesReturn | Sales | entities-03 |
| DB-SALE-008 | SalesReturnItem | Sales | entities-03 |
| DB-CRM-001 | Doctor | CRM | entities-04 |
| DB-CRM-002 | DoctorChamber | CRM | entities-04 |
| DB-CRM-003 | DoctorMedicine | CRM | entities-04 |
| DB-CRM-004 | DoctorVisit | CRM | entities-04 |
| DB-CRM-005 | DoctorVisitSample | CRM | entities-04 |
| DB-CRM-006 | Representative | CRM | entities-04 |
| DB-CRM-007 | RepresentativeAssignment | CRM | entities-04 |
| DB-CRM-008 | Territory | CRM | entities-04 |
| DB-CRM-009 | RepresentativeTarget | CRM | entities-04 |
| DB-FIN-001 | FinancialAccount | Finance | entities-04 |
| DB-FIN-002 | FinancialTransaction | Finance | entities-04 |
| DB-FIN-003 | Expense | Finance | entities-04 |
| DB-FIN-004 | ExpenseCategory | Finance | entities-04 |
| DB-FIN-005 | Income | Finance | entities-04 |
| DB-FIN-006 | IncomeCategory | Finance | entities-04 |
| DB-FIN-007 | FiscalPeriod | Finance | entities-04 |
| DB-SYS-001 | AuditLog | Audit | entities-04 |
| DB-SYS-002 | Notification | Platform | entities-04 |
| DB-SYS-003 | NotificationTemplate | Platform | entities-04 |
| DB-SYS-004 | Setting | Platform | entities-04 |
| DB-SYS-005 | IdempotencyKey | Platform | entities-04 |
| DB-SYS-006 | Attachment | Platform | entities-04 |
| DB-SYS-007 | ReportJob | Reporting | entities-04 |

**Total entities: 63.**

---

## Phase 3 Footer (required format)

### Key decisions recorded
1. **UUIDv7 primary keys** with monotonic `seq` on ledgers (P-05); document numbers remain the human/business identifier.
2. **Four orthogonal status dimensions** for invoices/purchases (state-machines §1) persisted as separate columns.
3. **`business_date` columns** added to all documents for correct local-date reporting (EC-041).
4. **Pseudo-batch `DEFAULT`** auto-created per branch for `no_batch` items so inventory remains uniform (EC-042).
5. **Batch actual cost** confirmed final (DEC-008): bonus allocated; immutable after confirm.
6. **Lock ordering fixed** for all money/stock transactions (see ledgers-costing-integrity §4).
7. **Soft close boundaries:** `StockAdjustment` and `Expense` cannot post into locked periods; only Owner override (BR-FIN-007).
8. **Opening balances** are `OPENING` transactions in the respective ledgers; never synthetic documents (BR-FIN-006).

### New assumptions
| ID | Assumption | Impact if wrong |
|---|---|---|
| A-041 | UUIDv7 support available (PostgreSQL ≥ 13 with app-side generation) — generated in the application, not the DB | Switch to ULID generation; portable change |
| A-042 | One `StockBalance` row per (branch, medicine, batch); no separate warehouse dimension (per A-002) | Warehouse dimension added to key + indexes |

### Risks identified in this phase

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-012 | Cache/ledger drift from missed code paths | Medium | High | Single choke-point service for all balance mutations; nightly reconciliation; integration tests |
| RISK-013 | Deadlocks under multi-batch multi-party contention | Medium | Medium | Fixed lock ordering, bounded retries, concurrency test suite |
| RISK-014 | UUIDv7 index bloat on very large ledgers | Low | Medium | Partitioning readiness + `seq` ordering for scans (NFR-SCALE-002) |
| RISK-015 | Soft-delete filtering omitted in a query → ghost records | Medium | Medium | Default manager filters `deleted_at IS NULL`; code review + tests |
| RISK-016 | Decimal mishandling in reporting aggregation | Low | High | DB-side aggregates with NUMERIC; serializer rounding rules tested |

### Unresolved items
- Q-013 (draft stock reservation) unchanged — model supports adding a `StockReservation` entity later without redesign.
- Q-016 (stock counting) — `StockCount`/`StockCountItem` entities deferred to Phase 2 backlog.
- Whether `DoctorCategory` should be configurable per company — currently a text enum; low impact.

### Phase 3 completion checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Bounded modules defined with ownership and dependency direction | ✅ |
| 2 | Every entity has purpose, fields, types, required flags, validation, relationships | ✅ |
| 3 | Unique constraints, indexes, status fields, soft-delete and audit behavior defined | ✅ |
| 4 | Text ERD covers 1:1, 1:N, M:N and join tables | ✅ |
| 5 | Four ledgers designed with derivation and reconciliation | ✅ |
| 6 | Costing model chosen and justified | ✅ |
| 7 | Decimal precision, constraints, locking and oversell prevention specified | ✅ |
| 8 | Traceability updated (FR/UC → DB entities) | ✅ |

### Information carried into Phase 4 (Architecture)
- Module boundaries and dependency direction → Django app layout and import rules.
- Entity ownership → service layer APIs between modules.
- Ledger choke-points and lock ordering → transaction design, Celery reconciliation jobs.
- Status dimensions and overrides → serializers/validators and reporting joins.
- `IdempotencyKey` and audit requirements → middleware design.
- Async needs (alerts, reopen reports, reconciliation) → Celery task inventory.

---

*End of Phase 3 overview. Continue to `docs/03-domain/ledgers-costing-integrity.md` and `docs/04-erd.md`.*
