# Requirements Traceability Matrix (RTM)

**Document ID:** DOC-TRC-001
**Status:** Living document — rows are completed as later phases are produced
**Parent:** `docs/01-requirements-specification.md`

> **Purpose.** Guarantee that every requirement is implemented, exposed, screenable, and testable — and that no artifact exists without a requirement behind it.

**Chain:** `FR → UC → DB entity → API → SCR → TC`

**Status legend:** ✅ complete · 🟡 in progress (source artifact authored, downstream pending) · ⬜ pending phase

---

## 1. Maintenance Protocol

1. **Phase 1** seeds this file with all FR groups and the key end-to-end flows.
2. **Phase 2** adds UC IDs for every use case and fills the `UC` column for affected FRs.
3. **Phase 3** fills `DB` (entity names must match the entity catalog).
4. **Phase 5** fills `API` (every endpoint traces to ≥ 1 FR; every FR with a UI effect traces to ≥ 1 endpoint, excluding pure UI rules).
5. **Phase 6** fills `SCR` (every screen traces to ≥ 1 FR).
6. **Phase 9** fills `TC` (every FR has ≥ 1 test case; critical FRs have multiple, including concurrency/negative tests).
7. **Gate check before Phase 12–13:** zero ⬜ rows. Orphan detection runs both directions.

**Validation rules**
- No FR may be marked implemented without a passing TC.
- No UC/DB entity/API/SCR/TC may exist without an FR ancestor (documentation defect otherwise).
- NFRs are traced to verification tests rather than screens/entities.

---

## 2. Seeded Rows — Critical End-to-End Flows

| FR | Requirement (short) | UC | DB | API | SCR | TC | Status |
|---|---|---|---|---|---|---|---|
| FR-AUTH-001 | Sign in (mobile/email + password) | UC-AUTH-001 | User, Session | `POST /api/v1/auth/login` | SCR-AUTH-LOGIN | TC-AUTH-001 | 🟡 |
| FR-AUTH-003 | Lockout after failed attempts | UC-AUTH-002 | User, LoginAttempt | `POST /api/v1/auth/login` | SCR-AUTH-LOGIN | TC-AUTH-002 | ⬜ |
| FR-AUTH-009/010 | JWT + refresh rotation/reuse detection | UC-AUTH-003 | Session, RefreshToken | `POST /api/v1/auth/refresh` | — | TC-AUTH-003/004 | ⬜ |
| FR-USER-001 | Create user with roles/branches | UC-USER-001 | User, UserRole, UserBranch | `POST /api/v1/users/` | SCR-USER-NEW | TC-USER-001 | ⬜ |
| FR-RBAC-003 | Role permission grants/denies | UC-RBAC-001 | Role, Permission, RolePermission | `PUT /api/v1/roles/{id}/permissions/` | SCR-ROLE-DETAIL | TC-RBAC-001 | ⬜ |
| FR-RBAC-009 | Branch object scoping (no IDOR) | UC-RBAC-002 | — (query layer) | all scoped endpoints | — | TC-SEC-001 | ⬜ |
| FR-BRANCH-003 | Branch-scoped documents | UC-BRANCH-001 | Branch (+ `branch_id` on all docs) | all scoped endpoints | SCR-BRANCH-SWITCH | TC-BRANCH-001 | ⬜ |
| FR-CAT-001 | Medicine CRUD | UC-CAT-001 | Medicine | `POST /api/v1/medicines/` | SCR-MED-LIST, SCR-MED-DETAIL | TC-CAT-001 | ⬜ |
| FR-CAT-007 | Near-expiry threshold per medicine | UC-CAT-002 | Medicine | `PATCH /api/v1/medicines/{id}/` | SCR-MED-DETAIL | TC-CAT-002 | ⬜ |
| FR-UNIT-003/004 | Pack conversions and validation | UC-UNIT-001 | Unit, MedicineUnitConversion | `POST /api/v1/medicines/{id}/conversions/` | SCR-MED-UNITS | TC-UNIT-001 | ⬜ |
| FR-BATCH-001 | Batch identity + merge on receipt | UC-BATCH-001 | MedicineBatch | `POST /api/v1/purchases/{id}/confirm/` | SCR-PUR-NEW | TC-BATCH-001 | ⬜ |
| FR-INV-002 | Stock ledger movement with source ref | UC-INV-001 | InventoryTransaction | internal (service) | SCR-INV-MOVEMENTS | TC-INV-001 | ⬜ |
| FR-INV-005 | FEFO batch preselection | UC-INV-002 | StockBalance, MedicineBatch | `GET /api/v1/inventory/fefo/` | SCR-SALE-NEW | TC-INV-002 | ⬜ |
| FR-INV-008/009 | No negative stock; concurrent safety | UC-INV-003 | StockBalance (+ check constraints) | `POST /api/v1/sales/{id}/confirm/` | — | TC-INV-003, TC-CONC-001 | ⬜ |
| FR-INV-020 | Cache↔ledger reconciliation job | UC-INV-004 | StockBalance, InventoryTransaction | `GET /api/v1/inventory/reconciliation/` | SCR-INV-RECON | TC-INV-004 | ⬜ |
| FR-ADJ-001/004 | Adjustment + write-off expense | UC-ADJ-001 | StockAdjustment, StockAdjustmentItem | `POST /api/v1/stock-adjustments/` | SCR-ADJ-NEW | TC-ADJ-001 | ⬜ |
| FR-SUP-001 | Supplier CRUD | UC-SUP-001 | Supplier | `POST /api/v1/suppliers/` | SCR-SUP-LIST, SCR-SUP-DETAIL | TC-SUP-001 | ⬜ |
| FR-SUP-005/007 | Supplier ledger and payable | UC-SUP-002 | SupplierLedgerEntry | `GET /api/v1/suppliers/{id}/ledger/` | SCR-SUP-LEDGER | TC-SUP-002 | ⬜ |
| FR-PUR-008 | Purchase confirmation atomic effects | UC-PUR-002 | Purchase, PurchaseItem, MedicineBatch, InventoryTransaction, SupplierLedgerEntry, FinancialTransaction | `POST /api/v1/purchases/{id}/confirm/` | SCR-PUR-NEW | TC-PUR-001 | ⬜ |
| FR-PUR-015 | Effective cost incl. bonus allocation | UC-PUR-002 | MedicineBatch (`unit_cost`) | `POST /api/v1/purchases/{id}/confirm/` | SCR-PUR-NEW | TC-PUR-002 | ⬜ |
| FR-PUR-006 | Duplicate supplier invoice blocked/override | UC-PUR-003 | Purchase | `POST /api/v1/purchases/{id}/confirm/` | SCR-PUR-NEW | TC-PUR-003 | ⬜ |
| FR-PPAY-002 | Supplier payment allocation (FIFO/manual) | UC-PPAY-001 | Payment (supplier), PaymentAllocation | `POST /api/v1/supplier-payments/` | SCR-SUP-PAY | TC-PPAY-001 | ⬜ |
| FR-PRET-005 | Debit note reduces payable/advance | UC-PRET-001 | PurchaseReturn, PurchaseReturnItem, SupplierLedgerEntry | `POST /api/v1/purchase-returns/{id}/confirm/` | SCR-PRET-NEW | TC-PRET-001 | ⬜ |
| FR-CUST-001 | Customer CRUD | UC-CUST-001 | Customer | `POST /api/v1/customers/` | SCR-CUST-LIST, SCR-CUST-DETAIL | TC-CUST-001 | ⬜ |
| FR-CUST-002/007 | Credit terms and AR aging | UC-CUST-002 | Customer, CustomerLedgerEntry | `GET /api/v1/reports/ar-aging/` | SCR-CUST-LEDGER | TC-CUST-002 | ⬜ |
| FR-SALE-015 | Sale confirmation atomic effects | UC-SALE-002 | SalesInvoice, SalesInvoiceItem, InventoryTransaction, CustomerLedgerEntry, FinancialTransaction | `POST /api/v1/sales/{id}/confirm/` | SCR-SALE-NEW | TC-SALE-001 | ⬜ |
| FR-SALE-016 | Gapless invoice numbering | UC-SALE-002 | DocumentSequence, SalesInvoice | `POST /api/v1/sales/{id}/confirm/` | SCR-INVOICE-DETAIL | TC-SALE-002 | ⬜ |
| FR-SALE-005/009 | Below-cost & credit overrides | UC-SALE-003 | SalesInvoice (override metadata) | `POST /api/v1/sales/{id}/confirm/` | SCR-SALE-NEW | TC-SALE-003/004 | ⬜ |
| FR-SALE-018/019 | Cancellation rules | UC-SALE-004 | SalesInvoice (status/reversal) | `POST /api/v1/sales/{id}/cancel/` | SCR-INVOICE-DETAIL | TC-SALE-005 | ⬜ |
| FR-PAY-002 | FIFO auto-allocation with locks | UC-PAY-001 | Payment, PaymentAllocation | `POST /api/v1/payments/` | SCR-PAY-COLLECT | TC-PAY-001 | ⬜ |
| FR-PAY-004 | Partial payment status transitions | UC-PAY-002 | PaymentAllocation, SalesInvoice | `POST /api/v1/payments/` | SCR-PAY-COLLECT | TC-PAY-002 | ⬜ |
| FR-PAY-009 | Payment reversal rules | UC-PAY-003 | Payment (reversal), PaymentAllocation | `POST /api/v1/payments/{id}/reverse/` | SCR-PAY-DETAIL | TC-PAY-003 | ⬜ |
| FR-PAY-017 | Duplicate payment protection (idempotency) | UC-PAY-001 | IdempotencyKey | `POST /api/v1/payments/` | — | TC-CONC-002 | ⬜ |
| FR-SRET-004 | Restock vs quarantine on return | UC-SRET-001 | SalesReturn, SalesReturnItem, InventoryTransaction | `POST /api/v1/sales-returns/{id}/confirm/` | SCR-SRET-NEW | TC-SRET-001 | ⬜ |
| FR-SRET-005/007 | Credit note + invoice return status | UC-SRET-001 | SalesReturn, CustomerLedgerEntry, SalesInvoice | `POST /api/v1/sales-returns/{id}/confirm/` | SCR-SRET-NEW | TC-SRET-002 | ⬜ |
| FR-DOC-007 | Doctor–medicine mapping | UC-DOC-002 | Doctor, DoctorMedicine | `POST /api/v1/doctors/{id}/medicines/` | SCR-DOC-DETAIL | TC-DOC-001 | ⬜ |
| FR-DVIS-002/003 | Visit log + sample issue from promo stock | UC-DVIS-001 | DoctorVisit, DoctorVisitSample, InventoryTransaction | `POST /api/v1/doctor-visits/` | SCR-DVIS-NEW | TC-DVIS-001 | ⬜ |
| FR-DVIS-006 | Coverage planned vs actual | UC-DVIS-002 | DoctorVisit, DoctorVisitPlan | `GET /api/v1/reports/visit-coverage/` | SCR-DVIS-REPORTS | TC-DVIS-002 | ⬜ |
| FR-REP-008 | Rep-wise sales report | UC-REP-001 | SalesInvoice (`sales_rep_id`) | `GET /api/v1/reports/sales-by-rep/` | SCR-RPT-SALES-REP | TC-REP-001 | ⬜ |
| FR-EXP-003 | Expense approval threshold | UC-EXP-001 | Expense | `POST /api/v1/expenses/` | SCR-EXP-NEW | TC-EXP-001 | ⬜ |
| FR-INC-003 | Income posts to account | UC-INC-001 | Income, FinancialTransaction | `POST /api/v1/incomes/` | SCR-INC-NEW | TC-INC-001 | ⬜ |
| FR-FIN-013/014 | Gross and net profit | UC-FIN-001 | InventoryTransaction (COGS), SalesInvoice, Expense, Income | `GET /api/v1/reports/profit/` | SCR-RPT-PROFIT | TC-FIN-001 | ⬜ |
| FR-FIN-021 | Period lock control | UC-FIN-002 | FiscalPeriod | `POST /api/v1/periods/{id}/lock/` | SCR-SET-PERIODS | TC-FIN-002 | ⬜ |
| FR-RPT-018 | AR aging report | UC-RPT-001 | CustomerLedgerEntry | `GET /api/v1/reports/ar-aging/` | SCR-RPT-AR | TC-RPT-001 | ⬜ |
| FR-RPT-024 | Exception report (overrides) | UC-RPT-002 | AuditLog + document override flags | `GET /api/v1/reports/exceptions/` | SCR-RPT-EXCEPTIONS | TC-RPT-002 | ⬜ |
| FR-NOTIF-003 | Near-expiry alerts | UC-NOTIF-001 | Notification, MedicineBatch | Celery job + `GET /api/v1/notifications/` | SCR-NOTIF-CENTER | TC-NOTIF-001 | ⬜ |
| FR-AUD-001/002 | Audit capture and immutability | UC-AUD-001 | AuditLog | `GET /api/v1/audit-logs/` | SCR-AUD-LIST | TC-AUD-001 | ⬜ |
| FR-SET-005 | Numbering series configuration | UC-SET-001 | DocumentSequence | `PUT /api/v1/settings/numbering/` | SCR-SET-NUMBERING | TC-SET-001 | ⬜ |

## 3. Seeded Rows — Non-Functional Verification

| NFR | Requirement (short) | Verification | Phase | Status |
|---|---|---|---|---|
| NFR-SEC-004 | Rate limiting / brute force | TC-SEC-010 (auth throttle suite) | 9 | ⬜ |
| NFR-PERF-001 | API latency budgets | k6 load scenario LOAD-001 | 9 | ⬜ |
| NFR-REL-001 | ACID on financial/inventory ops | Fault-injection TC-REL-001 | 9 | ⬜ |
| NFR-DI-004 | Append-only ledgers | Schema/test audit TC-DATA-001 | 9 | ⬜ |
| NFR-AVL-001 | 99.5% uptime | External probe + monthly report | 10/13 | ⬜ |
| NFR-BAK-001 | RPO ≤ 15 min backup | Restore drill DR-001 | 10 | ⬜ |
| NFR-ACC-001 | WCAG 2.1 AA core flows | axe-core + manual audit TC-ACC-001 | 9 | ⬜ |
| NFR-MOB-002 | PWA install/offline read | PWA audit TC-MOB-001 | 9 | ⬜ |

---

## 4. Coverage Counters (updated per phase)

| Phase | FR covered by UC | FR covered by DB | FR covered by API | FR covered by SCR | FR covered by TC |
|---|---|---|---|---|---|
| 1 (seed) | 0 / 506 | 0 / 506 | 0 / 506 | 0 / 506 | 0 / 506 |
| 2 (analysis) | 95 UCs authored; every FR group has ≥ 1 UC; 50+ key FRs explicitly mapped above | 0 / 506 | 0 / 506 | 0 / 506 | 0 / 506 |
| 3 (domain) | — | 63 entities authored; all FR groups mapped to owning entities (entity ↔ UC maps in `entities-01…04`) | 0 / 506 | 0 / 506 | 0 / 506 |

*Counters are updated mechanically before each phase gate; the gate does not pass with orphan rows.*
