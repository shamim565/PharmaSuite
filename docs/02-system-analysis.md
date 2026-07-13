# Phase 2 — System Analysis

**Document ID:** DOC-SYS-001
**Version:** 1.0 (Phase 2 baseline)
**Status:** Complete — pending Batch B review
**Parent:** `docs/01-requirements-specification.md`
**Related:** `docs/assumptions-log.md`, `docs/open-questions.md`, `docs/01-requirements/08-business-rules.md`

---

## Phase 2 Header (required format)

**Objective.** Translate the Phase 1 requirements into an actor/use-case model, complete workflows, edge-case handling, and state transitions — the bridge between requirements and domain design.

**Expected deliverables.**
1. Actor catalog — this document, §1
2. Use-case catalog with full flows (95 use cases) — `docs/02-analysis/use-cases-01.md`, `use-cases-02.md`
3. Textual workflow diagrams (10 flows) — `docs/02-analysis/workflows.md`
4. Edge-case catalog (~42 cases) — `docs/02-analysis/edge-cases.md`
5. State transition specification — `docs/02-analysis/state-machines.md`

**Decisions inherited from Phase 1.** DEC-001…DEC-010, A-001…A-040, BR-DATA/AUTH/RBAC/BRANCH/DOC/AUD/IDEMP/INV/BATCH/PUR/SALE/PAY/SRET/FIN/CRM rule sets; 506 FRs.

**Unresolved business decisions.** The 48 questions in `docs/open-questions.md`; defaults apply where referenced.

**Assumptions.** No new assumptions in Phase 2 beyond Phase 1; two clarifications are recorded in the footer.

---

## 1. Actor Catalog

| Actor | Type | Description & goals | Branch scope | Primary modules |
|---|---|---|---|---|
| **Owner** | Internal, human | Business owner. Wants consolidated profit, dues, stock health, and control. Approves high-risk actions (period override, large write-offs). | All branches | All modules |
| **Super Admin** | Internal, human | System steward. Manages users, roles, branches, settings, integrations, audit. Not necessarily a business approver. | All branches | Identity, settings, audit |
| **Admin** | Internal, human | Operations administrator. Masters data, approvals within thresholds, day-to-day administration. | Assigned branches (typically all) | Catalog, approvals, reporting |
| **Accountant** | Internal, human | Owns money flows: payments, allocations, ledgers, expenses, income, account reconciliation, VAT summaries, period close support. | Assigned branches + company accounts | Payments, finance, reports |
| **Sales Operator** | Internal, human | Counter/order-desk user. Creates invoices, collects payments, manages customer interactions. Fast, accurate entry is the priority. | Assigned branch | Sales, payments, customers |
| **Warehouse Manager** | Internal, human | Receiving, storage, batch/expiry integrity, dispatch, adjustments. | Assigned branch | Purchases, inventory, batches |
| **Branch Manager** | Internal, human | Runs a branch. Approves discounts/overrides within thresholds, monitors KPIs and staff. | Own branch(es) | Approvals, reports, CRM |
| **Sales Representative** | Internal, human | Field sales. Customer coverage, order support, collection support; views own performance and assigned customers. | Assigned branch(es) | Customers, sales views |
| **Medical Representative (MR)** | Internal, human | Doctor coverage. Plans/logs visits, distributes samples, maintains doctor–medicine mappings. Mobile-heavy. | Assigned branch(es) | Doctors, visits, promo stock |
| **Customer** | External, human | Receives invoices/statements and makes payments; no system login in MVP (portal is future). | n/a | — |
| **Supplier** | External, human | Supplies goods; receives purchase docs/debit notes/statements; no system login in MVP. | n/a | — |
| **System (Celery/automation)** | Internal, non-human | Nightly reconciliation, expiry/low-stock alerts, async report generation, scheduled notifications, backup hooks. | All (system scope) | Notifications, reports, integrity |

### 1.1 Actor notes
- Roles are implemented with **role → permission grants**; one user may hold multiple roles (FR-USER-007).
- External actors interact only through documents (PDF/share) in MVP; portals are Phase 2/FUT (Q-045).
- The System actor always acts under a named technical identity so its audit entries are attributable.

---

## 2. Use-Case Index

Full specifications: `docs/02-analysis/use-cases-01.md` (UC-01) and `use-cases-02.md` (UC-02).

| UC ID | Name | Primary actor | Key FRs |
|---|---|---|---|
| UC-AUTH-001 | Sign in | All | FR-AUTH-001,002,009,016 |
| UC-AUTH-002 | Handle account lockout | System/SA | FR-AUTH-003,017 |
| UC-AUTH-003 | Refresh session securely | System | FR-AUTH-009,010 |
| UC-AUTH-004 | Reset forgotten password | All | FR-AUTH-005,006,008 |
| UC-AUTH-005 | Logout all devices | All/SA | FR-AUTH-012,013 |
| UC-AUTH-006 | Manage TOTP 2FA | Adm+ | FR-AUTH-015 |
| UC-USER-001 | Create user with roles/branches | Adm+ | FR-USER-001,002,007,008 |
| UC-USER-002 | Deactivate/reactivate user | Adm+ | FR-USER-004,005,009 |
| UC-USER-003 | Admin-reset user password | Adm+ | FR-USER-003,014 |
| UC-USER-004 | Review user activity | Adm+ | FR-USER-013 |
| UC-RBAC-001 | Manage role permissions | SA | FR-RBAC-001,003,006,012 |
| UC-RBAC-002 | Enforce branch-scoped access | System | FR-RBAC-009, FR-BRANCH-012 |
| UC-BRANCH-001 | Manage branches | SA/Owner | FR-BRANCH-001,002,007 |
| UC-BRANCH-002 | Switch branch context | All | FR-BRANCH-004,005 |
| UC-CAT-001 | Create/edit medicine | WM/Adm | FR-CAT-001…011 |
| UC-CAT-002 | Configure expiry thresholds & margin floor | Adm | FR-CAT-007,024, FR-SET-008,010 |
| UC-CAT-003 | Manage generics/manufacturers/categories | Adm | FR-CAT-016,017,018 |
| UC-CAT-004 | Import/export catalog | Adm | FR-CAT-014 |
| UC-CAT-005 | Merge duplicate medicine | Adm | FR-CAT-015 |
| UC-UNIT-001 | Manage unit & pack conversions | WM | FR-UNIT-001…008 |
| UC-BATCH-001 | Batch create/merge on receipt | System/WM | FR-BATCH-001,002,004 |
| UC-BATCH-002 | Mark batch recalled | WM/QA | FR-BATCH-012 |
| UC-BATCH-003 | Correct batch expiry before movement | WM/Adm | FR-BATCH-015 |
| UC-INV-001 | Post stock movement | System | FR-INV-001,002 |
| UC-INV-002 | FEFO batch selection / override | SO/BM | FR-INV-005,006, FR-BATCH-009,010 |
| UC-INV-003 | Atomic availability validation | System | FR-INV-007,008,009 |
| UC-INV-004 | Reconcile cached vs ledger stock | System/Acct | FR-INV-020 |
| UC-INV-005 | View stock & expiry reports | WM/BM | FR-INV-011…018, FR-RPT-010…016 |
| UC-ADJ-001 | Create stock adjustment | WM/BM | FR-ADJ-001,002,005 |
| UC-ADJ-002 | Approve/reject adjustment | BM/Adm | FR-ADJ-003 |
| UC-ADJ-003 | Write off expired/damaged stock | WM/BM | FR-ADJ-004, FR-BATCH-010,011 |
| UC-SUP-001 | Manage supplier | WM/Acct | FR-SUP-001…014 |
| UC-SUP-002 | View supplier ledger/statement | Acct | FR-SUP-005,006,007,008 |
| UC-SUP-003 | Post supplier opening balance | Acct | FR-SUP-004, FR-FIN-022 |
| UC-PUR-001 | Create purchase draft | WM | FR-PUR-001…007,015 |
| UC-PUR-002 | Confirm purchase / receive stock | WM | FR-PUR-008,009,010, FR-BATCH-001 |
| UC-PUR-003 | Handle duplicate supplier invoice | WM/Adm | FR-PUR-006, BR-PUR-003 |
| UC-PUR-004 | Cancel confirmed purchase | Adm | FR-PUR-013, BR-PUR-006 |
| UC-PPAY-001 | Pay supplier with allocation | Acct | FR-PPAY-001…009 |
| UC-PPAY-002 | Reverse supplier payment | Acct/Owner | FR-PPAY-004 |
| UC-PPAY-003 | Supplier cheque lifecycle | Acct | FR-PPAY-007 |
| UC-PRET-001 | Create/confirm purchase return | WM | FR-PRET-001…006,008 |
| UC-PRET-002 | Handle pending pickup | WM | FR-PRET-014 |
| UC-CUST-001 | Manage customer | SO/Adm | FR-CUST-001…013 |
| UC-CUST-002 | View customer ledger/aging | Acct | FR-CUST-005…007 |
| UC-CUST-003 | Set credit terms / credit hold | Adm/Acct | FR-CUST-002,017 |
| UC-SALE-001 | Create draft sale | SO | FR-SALE-001…008,011…014 |
| UC-SALE-002 | Confirm sale | SO/System | FR-SALE-015…017,025,026,038 |
| UC-SALE-003 | Override below-cost/credit controls | BM/Owner | FR-SALE-005,009,030, BR-SALE-005,006 |
| UC-SALE-004 | Cancel invoice | Adm | FR-SALE-018,019, BR-SALE-008,009 |
| UC-SALE-005 | Reprint/share invoice | SO | FR-SALE-020,021,022 |
| UC-SALE-006 | Sale with payment at entry | SO/Acct | FR-SALE-010, FR-PAY-001…007 |
| UC-PAY-001 | Collect payment (FIFO allocation) | Acct/SO | FR-PAY-001…007,017 |
| UC-PAY-002 | Apply partial payment | System | FR-PAY-004, FR-SALE-025 |
| UC-PAY-003 | Reverse payment | Acct/Owner | FR-PAY-009, BR-PAY-004 |
| UC-PAY-004 | Collect old due from due list | Acct/SO | FR-PAY-016, FR-CUST-007 |
| UC-PAY-005 | Customer cheque lifecycle | Acct | FR-PAY-013 |
| UC-PAY-006 | Apply customer advance | Acct/System | FR-PAY-005,018 |
| UC-SRET-001 | Process sales return (restock/quarantine) | SO/WM | FR-SRET-001…005,010,016 |
| UC-SRET-002 | Refund via credit note | Acct | FR-SRET-005,006 |
| UC-SRET-003 | No-invoice return (exception) | Adm | FR-SRET-008, BR-SRET-006 |
| UC-DOC-001 | Manage doctor | MR/Adm | FR-DOC-001…006,010,014 |
| UC-DOC-002 | Map medicines to doctor | MR/BM | FR-DOC-007…009 |
| UC-DOC-003 | View doctor attributed sales | BM | FR-DOC-012 |
| UC-DVIS-001 | Log visit with samples | MR | FR-DVIS-001,002,003,009 |
| UC-DVIS-002 | Plan visits | MR/BM | FR-DVIS-001,010 |
| UC-DVIS-003 | View coverage report | BM | FR-DVIS-005,006,007 |
| UC-REP-001 | View rep performance | BM | FR-REP-008…010,014 |
| UC-REP-002 | Assign customers/doctors/territories | BM | FR-REP-003,004,005,011 |
| UC-REP-003 | Set targets | BM/Owner | FR-REP-006,007 |
| UC-TER-001 | Manage territories | BM/Adm | FR-TER-001…005 |
| UC-EXP-001 | Record expense | Acct | FR-EXP-001,002,004 |
| UC-EXP-002 | Approve/reject expense | BM/Adm | FR-EXP-003, BR (thresholds) |
| UC-EXP-003 | Reverse expense | Acct/Owner | FR-EXP-005 |
| UC-INC-001 | Record other income | Acct | FR-INC-001…003 |
| UC-INC-002 | Reverse income | Acct/Owner | FR-INC-004 |
| UC-FIN-001 | View profit reports | Owner/BM | FR-FIN-013,014,027, FR-RPT-027 |
| UC-FIN-002 | Lock/unlock fiscal period | Owner | FR-FIN-021, BR-DOC-004 |
| UC-FIN-003 | Transfer between accounts | Acct | FR-FIN-005,009 |
| UC-FIN-004 | Reconcile ledgers | System/Acct | FR-FIN-020, NFR-REL-003 |
| UC-FIN-005 | Post deposit/withdrawal | Acct | FR-FIN-004 |
| UC-FIN-006 | View AR/AP aging | Acct | FR-FIN-011,012 |
| UC-FIN-007 | Month-end close pack | Acct/Owner | FR-FIN-017…021,027 |
| UC-RPT-001 | Generate/export report | All | FR-RPT-001…030, NFR-PERF-003 |
| UC-RPT-002 | View exception report | Owner | FR-RPT-024, BR-AUD-003 |
| UC-RPT-003 | Generate large report asynchronously | System | FR-RPT-030, A-027 |
| UC-NOTIF-001 | Receive alerts | All | FR-NOTIF-001…007 |
| UC-NOTIF-002 | Manage notification preferences | All | FR-NOTIF-008…012 |
| UC-AUD-001 | Review audit log | Owner/SA | FR-AUD-001…006,009 |
| UC-AUD-002 | Export audit extract | Owner | FR-AUD-007,008 |
| UC-SET-001 | Configure numbering series | Owner | FR-SET-005 |
| UC-SET-002 | Configure company & fiscal year | Owner | FR-SET-001,002,003,004 |
| UC-SET-003 | Configure approval thresholds | Owner | FR-SET-006, FR-RBAC-011 |
| UC-SET-004 | Configure templates & notification channels | Owner/Adm | FR-SET-012,013, FR-NOTIF-009,010,011 |
| UC-MIG-001 | Import opening data | Acct/SA | FR-FIN-022, A-036, Phase 11 |

**Total: 95 use cases.**

---

## 3. Cross-Cutting Analysis Themes

| Theme | Handling | References |
|---|---|---|
| Atomicity | Every confirm/cancel/reverse is one DB transaction; all-or-nothing effects | BR-DOC-005, BR-SALE-003 |
| Concurrency | Deterministic row locking (stock, invoice, customer), idempotency keys, bounded retries | BR-INV-010, BR-PAY-002, BR-AUD-004 |
| Reversibility | No destructive deletes; compensating entries; VOID/REVERSED statuses | BR-SALE-010, BR-PAY-001 |
| Branch isolation | Query-level scoping; cross-branch access indistinguishable from not-found | BR-BRANCH-002 |
| Auditability | Every state change audited with before/after; overrides require reasons | BR-AUD-001,003 |
| Failure handling | Idempotent retries; async work fails soft; alerts routed | NFR-REL, NFR-AVL-003 |
| Time | UTC storage, local business dates; day-boundary reports use business date | BR-DATA-005 |

---

## Phase 2 Footer (required format)

### Key decisions recorded
1. **Invoice/document state is modeled on orthogonal dimensions** (lifecycle, payment, return, fulfillment) rather than one mutable status enum; the displayed status is derived. The linear chain suggested in the brief (`Draft → Confirmed → Partially Paid → Paid → Cancelled → Partially Returned → Fully Returned`) cannot represent paid+partially-returned combinations; see `state-machines.md` §1.1 for the conflict analysis and resolution.
2. **Allocation and confirmation lock ordering is fixed**: stock rows (branch, medicine, batch) → invoice/customer rows → sequence rows. This prevents deadlocks and oversell.
3. **Async reports threshold** (A-027) confirmed as the standard escape hatch for heavy reports.
4. **External actors are document-based only in MVP** (no portal logins).

### Risks identified in this phase

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-008 | State explosion if UI shows raw orthogonal statuses | Medium | Medium | Single derived display status with filter facets (Phase 6 spec) |
| RISK-009 | Deadlocks under concurrent multi-batch sales | Medium | High | Fixed lock ordering + retry policy + concurrency test suite (Phase 9) |
| RISK-010 | Edge cases from offline PWA stale reads | Low | Medium | Server revalidation at confirm; idempotent retries (DEC-005) |
| RISK-011 | Use-case flows diverging from actual counter/warehouse practice | Medium | High | UAT scripts derived from these flows; pilot branch feedback (Phase 11) |

### Unresolved items
- Q-013 (reservation) and Q-011 remain open; flows assume no reservation (default). If the client later requires reservations, UC-SALE-001/002 and UC-INV-003 change; estimate provided on request.
- Q-029 (cheque) assumed enabled; if disabled, UC-PAY-005/UC-PPAY-003 are dropped.
- Controlled-medicine register (Q-047) may add a report-only scope.

### Phase 2 completion checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Actor catalog complete with branch scope and module ownership | ✅ |
| 2 | Use-case index covers every FR group | ✅ |
| 3 | Full use-case specs (pre/main/alt/exception/post) for all 95 UCs | ✅ |
| 4 | Workflow diagrams for all 10 required flows | ✅ |
| 5 | Edge cases identified with handling rules | ✅ |
| 6 | State machines with valid/invalid transitions | ✅ |
| 7 | Requirements traceability updated (FR → UC) | ✅ |
| 8 | Conflicts detected and resolved with rationale | ✅ |

### Information carried into Phase 3 (Domain & Data Design)
- UC main/alternative/exception flows define required entity operations, constraints, and status dimensions.
- Edge cases (especially concurrency and return paths) determine locking strategy and constraint design.
- State machines define status fields, transitions, and guard conditions for entities.
- Actor/branch scoping defines where ownership columns (`branch_id`, `created_by`) must exist.
- Workflows determine which ledger entries each document posts.

---

*End of Phase 2 overview. Continue to `docs/03-domain-model.md`.*
