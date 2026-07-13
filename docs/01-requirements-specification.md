# Software Requirements Specification — Medicine Dealer ERP

**Document ID:** DOC-SRS-001
**Version:** 1.0 (Phase 1 baseline)
**Status:** Complete — pending client review (Batch A gate)
**Supersedes:** none
**Related:** `docs/assumptions-log.md`, `docs/open-questions.md`, `docs/01-requirements/*`

---

## Phase 1 Header (required format)

**Objective.** Establish a complete, numbered, testable requirements baseline for the Medicine Dealer ERP and surface every business ambiguity before design begins.

**Expected deliverables.**
1. Business context and operating model — this document, §2
2. Scope definition (MVP / Phase 2 / Future / Out) — §3
3. Functional requirements catalog (`FR-*`) — `docs/01-requirements/fr-01…fr-08`
4. Non-functional requirements (`NFR-*`) — `docs/01-requirements/07-non-functional-requirements.md`
5. Business rules (`BR-*`) — `docs/01-requirements/08-business-rules.md`
6. Client questionnaire (`Q-*`) — `docs/open-questions.md`
7. Assumptions and locked decisions — `docs/assumptions-log.md`
8. Seed traceability matrix — `docs/22-requirements-traceability-matrix.md`

**Decisions inherited from Phase 0 (brief).**
- FR/NFR coverage list, target stack (Next.js/TypeScript/Tailwind/shadcn/TanStack/RHF+Zod/Zustand; Django/DRF/PostgreSQL/Redis/Celery/S3), modular monolith, API-first, PostgreSQL source of truth, backend owns business rules, multi-branch from day one, desktop→PWA→possible Flutter, no microservices.

**Decisions inherited from Batch A gate (see assumptions log).**
- DEC-001 Bangladesh/BDT/VAT 15%/July–June; DEC-002 subledgers only, no GL; DEC-003 branch-isolated stock, transfers Phase 2; DEC-004 VM + Docker Compose + managed data services; DEC-005 PWA offline read shell, no offline write queue.

**Unresolved business decisions.** 48 questions in `docs/open-questions.md`. None block Phase 1–2 work because each has a safe default already embedded in the requirements.

**Assumptions.** 40 tracked in `docs/assumptions-log.md` (A-001…A-040).

---

## 1. Purpose, Audience and Conventions

### 1.1 Purpose
This SRS is the contract between the business and the delivery team for **what** the system must do. It is written to be verifiable: every requirement has an ID, an actor, a priority, and acceptance criteria. **How** the system does it is defined in Phases 3–5.

### 1.2 Audience
Business owner and managers (scope validation), product team (backlog source), backend/frontend engineers (constraints), QA (test basis), DevOps (non-functional constraints), and the client's accountant/warehouse stakeholders (workflow validation).

### 1.3 Priority tags

| Tag | Meaning |
|---|---|
| `M` | MVP must-have (Sprints 1–8 scope) |
| `S` | MVP should-have (implemented if the sprint allows; otherwise first Phase 2 item) |
| `P2` | Phase 2 — confirmed later scope |
| `FUT` | Future roadmap — captured, not scheduled |

### 1.4 Requirement quality rules
- Each FR states one behavior or one cohesive group of behaviors around one object; it is independently testable.
- Acceptance criteria are stated as observable outcomes, not implementation details.
- Business rules (`BR-*`) are referenced where relevant; rules are normative.
- Conflicts between requirements are resolved in favor of: statutory requirement > business rule > NFR > convenience.

### 1.5 Document map

| Document | Content |
|---|---|
| `01-requirements-specification.md` | This overview: context, scope, conventions, phase gate |
| `01-requirements/fr-01-identity-rbac-branch.md` | FR-AUTH, FR-USER, FR-RBAC, FR-BRANCH |
| `01-requirements/fr-02-catalog-units.md` | FR-CAT, FR-UNIT |
| `01-requirements/fr-03-batches-inventory-adjustments.md` | FR-BATCH, FR-INV, FR-ADJ |
| `01-requirements/fr-04-suppliers-purchases.md` | FR-SUP, FR-PUR, FR-PPAY, FR-PRET |
| `01-requirements/fr-05-customers-sales-payments-returns.md` | FR-CUST, FR-SALE, FR-PAY, FR-SRET |
| `01-requirements/fr-06-doctors-representatives-crm.md` | FR-DOC, FR-DVIS, FR-REP, FR-TER |
| `01-requirements/fr-07-finance-expenses-income-accounts.md` | FR-EXP, FR-INC, FR-FIN |
| `01-requirements/fr-08-reports-platform-settings.md` | FR-RPT, FR-DASH, FR-SRCH, FR-NOTIF, FR-AUD, FR-SET |
| `01-requirements/07-non-functional-requirements.md` | NFR-* |
| `01-requirements/08-business-rules.md` | BR-* |

---

## 2. Business Context

### 2.1 Business model
The client is a **medicine distributor/dealer**. It purchases medicines from manufacturers/importers (often with trade discounts and free/bonus quantities), stores them in branch warehouses with batch and expiry control, and sells to pharmacies, retailers, clinics and hospitals. Sales are frequently **on credit** (30/45/60-day terms), producing receivables that must be actively collected. The business promotes medicines through **medical representatives (MRs)** who visit doctors; doctor prescribing influences demand. Margin comes from the difference between the effective purchase cost (after discounts and bonus allocation) and the selling price.

### 2.2 Stakeholders and users

| Actor | Primary goals in the system |
|---|---|
| Owner | Consolidated profit, dues, branch performance; full control; no surprises |
| Super Admin | System configuration, users, roles, branches, data integrity |
| Admin | Day-to-day administration across branches |
| Accountant | Payments, dues, ledgers, expenses, income, account reconciliation, reports |
| Sales Operator | Fast, accurate invoicing, payment collection, customer lookup |
| Warehouse Manager | Receiving, batch/expiry accuracy, stock corrections, dispatch |
| Branch Manager | Branch P&L, approvals, staff supervision, stock health |
| Sales Representative | Customer coverage, order/collection support, sales reporting |
| Medical Representative (MR) | Doctor coverage, visit logging, sample tracking, product promotion |
| Customer (external) | Accurate invoices, correct dues, returns handled quickly |
| Supplier (external) | Accurate POs/receipts, debit notes, timely payment |

### 2.3 Current pain points (problem statements)
1. **Expiry losses** — stock is discovered expired during manual checks; no FEFO discipline.
2. **Unrecoverable dues** — credit sales recorded in registers/Excel; aging is invisible until it is too late.
3. **Unknown true profit** — purchase bonus, discounts, and returns are not factored into cost.
4. **Stock inaccuracy** — batch stock counts disagree between warehouse, sales desk, and books.
5. **No accountability** — anyone can change records; no audit trail; discounts and write-offs are undocumented.
6. **Multi-branch blindness** — consolidation requires manual effort; inter-branch comparisons impossible.
7. **Slow month-end** — reports are assembled by hand; VAT summaries are error-prone.
8. **Field activity invisible** — doctor coverage and MR productivity cannot be measured.

### 2.4 Main operational workflows (as-is → to-be)

| Workflow | To-be flow (summary) |
|---|---|
| Procurement | Select supplier → enter purchase (batch, expiry, qty, bonus, VAT) → confirm → stock + payable posted → pay (full/partial) → return defective/expired items with debit note |
| Stock management | Batch-received stock under FEFO → near-expiry alerts → adjustments/write-offs with approval → stock reports |
| Sales | Select customer → build invoice (FEFO batches, price by tier, discount rules, VAT) → confirm → stock deducted, invoice numbered → print/share → collect full/partial later |
| Due collection | Due list → aging → collect payment → auto-FIFO allocation or manual → receipt → ledger updated |
| Sales returns | Return against invoice → inspection (resellable/damaged) → stock restocked or quarantined → credit note / refund / due adjustment |
| Field ops | Plan visits → MR logs visit + samples → doctor-wise sales and visit coverage reports |
| Finance | Expenses/income posted to cash/bank/MFS accounts → receivables/payables aging → P&L |
| Month-end | Period lock → VAT summary → stock valuation → dues aging → P&L pack |

### 2.5 Expected business benefits (measurable)
- Reduce expiry write-off value by ≥ 50% within 6 months (FEFO + alerts).
- Reduce dues older than 60 days by ≥ 20% within 6 months (aging + collection workflow).
- Eliminate unrecorded free-good/sample leakage (promotional stock tracking).
- Month-end close reduced from days to same-day report generation.
- Zero unauthorized price/discount/write-off changes (permissions + audit).
- Single source of truth across branches within one fiscal quarter of go-live.

---

## 3. Scope

### 3.1 MVP (Sprints 1–8)
Identity, users, roles, permissions, branches; medicine catalog (generics, manufacturers, categories, units/pack conversions); batches; inventory and stock ledger; FEFO; suppliers and ledgers; purchases with bonus and VAT; purchase payments and returns; customers and ledgers; sales/invoices; partial payments and due collection; payment allocation; sales returns; doctors and doctor–medicine mapping; doctor visits; representatives and territories; expenses; other income; cash/bank/MFS accounts; receivables/payables; gross/net profit; expired/damaged stock handling; stock adjustment; core reports; search/filters; notifications (in-app + configurable email/SMS hooks); audit logs; settings; responsive desktop/tablet/mobile web + installable PWA.

### 3.2 Phase 2
Inter-branch stock transfers; purchase orders; sales orders; barcode scanning; SMS/WhatsApp due reminders and invoice sharing; advanced approval workflows; stock counting/verification; representative commissions; price lists/quantity breaks; GPS + photo visit evidence; scheduled email reports; cheque post-dated tracking; customer/supplier statements auto-email; thermal/POS receipt printing; Bangla UI.

### 3.3 Future
Flutter native app (offline-first field use); double-entry GL and financial statements; demand forecasting/reorder suggestions; customer portal; supplier portal; e-commerce ordering; advanced analytics/BI; e-signature; loyalty/schemes engine; multi-company; multi-currency.

### 3.4 Explicitly out of scope
Manufacturing/production; HR and payroll; fixed-asset management; fleet/route optimization; insurance claims; statutory regulatory filings (automated); prescription OCR; medical diagnosis data; microservices; blockchain; AI/ML features; hardware integration (weighing scales, automated dispensers).

---

## 4. Functional Requirements — Module Map

Full statements with IDs, actors, priorities and acceptance criteria are in the domain files.

| Domain file | Modules | Approx. FRs |
|---|---|---|
| `fr-01-identity-rbac-branch.md` | FR-AUTH (20), FR-USER (15), FR-RBAC (15), FR-BRANCH (12) | 62 |
| `fr-02-catalog-units.md` | FR-CAT (28), FR-UNIT (8) | 36 |
| `fr-03-batches-inventory-adjustments.md` | FR-BATCH (15), FR-INV (25), FR-ADJ (10) | 50 |
| `fr-04-suppliers-purchases.md` | FR-SUP (18), FR-PUR (30), FR-PPAY (10), FR-PRET (14) | 72 |
| `fr-05-customers-sales-payments-returns.md` | FR-CUST (20), FR-SALE (38), FR-PAY (20), FR-SRET (16) | 94 |
| `fr-06-doctors-representatives-crm.md` | FR-DOC (24), FR-DVIS (12), FR-REP (16), FR-TER (6) | 58 |
| `fr-07-finance-expenses-income-accounts.md` | FR-EXP (12), FR-INC (8), FR-FIN (30) | 50 |
| `fr-08-reports-platform-settings.md` | FR-RPT (30), FR-DASH (8), FR-SRCH (6), FR-NOTIF (12), FR-AUD (10), FR-SET (18) | 84 |
| **Total functional** | | **~506** |
| `07-non-functional-requirements.md` | 16 NFR categories | ~59 |
| `08-business-rules.md` | 13 rule groups | ~65 |

---

## 5. Traceability Approach

Every requirement is traceable in `docs/22-requirements-traceability-matrix.md`:

`FR → UC (Phase 2) → DB entity (Phase 3) → API (Phase 5) → SCR (Phase 6) → TC (Phase 9)`

Rules:
- No FR may be marked "done" without at least one passing TC.
- Every API endpoint maps to ≥ 1 FR or is explicitly infrastructure/internal.
- Every screen maps to ≥ 1 FR.
- Reverse traceability must also hold: every UC/DB/API/SCR/TC must trace back to an FR; orphans are defects in documentation.

---

## Phase 1 Footer (required format)

### Key decisions recorded
- DEC-001…DEC-010 (see `docs/assumptions-log.md`).
- 40 assumptions baselined (A-001…A-040), each with impact-if-wrong.
- 48 open questions published with recommended defaults (Q-001…Q-048).

### Risks identified in this phase

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-001 | Client answers to open questions arrive after procurement/sales design starts | High | High | Safe defaults implemented; answers gated before Sprint 3; change control cost stated per question |
| RISK-002 | Invoice/letterhead/Mushak samples not provided before Sprint 4 | Medium | Medium | Generic configurable templates ready; swap when samples arrive |
| RISK-003 | "Sales bonus" and "purchase bonus" meanings are conflated by stakeholders | Medium | Medium | Definitions locked in BR-SALE/BR-PUR; Q-038 separates samples; schemes scope clarified |
| RISK-004 | Multi-warehouse or transfers demanded mid-MVP | Medium | High | DEC-003; change control estimate provided |
| RISK-005 | Legacy data quality (opening stock/batches, dues) worse than expected | High | High | Phase 11 templates + dry-run reconciliation; pilot branch first |
| RISK-006 | Regulated medicines require registers not in scope | Low | High | Flagged in Q-047; license requirements to be confirmed by client's compliance contact |
| RISK-007 | Field staff resist mobile/PWA workflows | Medium | High | Mobile-first sale/collection/visit flows; pilot training; A-039 assumptions |

### Unresolved items
- 48 questions pending client answers (non-blocking).
- Client invoice/report sample formats pending.
- Existing data source inventory pending (Q-046).
- Final go-live pilot branch and date pending (Q-048).

### Phase 1 completion checklist

| # | Criterion | Status |
|---|---|---|
| 1 | Business context documented (model, users, pain, workflows, benefits) | ✅ |
| 2 | Scope split into MVP / Phase 2 / Future / Out | ✅ |
| 3 | Functional requirements cataloged with IDs, actors, priorities, acceptance criteria | ✅ |
| 4 | Non-functional requirements documented with measurable targets | ✅ |
| 5 | Business rules documented and cross-referenced | ✅ |
| 6 | Client questionnaire published with defaults and consequences | ✅ |
| 7 | Decisions and assumptions logged with impact analysis | ✅ |
| 8 | Traceability matrix seeded and process defined | ✅ |
| 9 | Phase risks recorded with mitigations | ✅ |
| 10 | No implementation work started | ✅ |

### Information carried into Phase 2 (System Analysis)
- The FR catalog (IDs, actors, acceptance criteria) is the use-case source.
- The business rules set is the primary source for use-case main/alternative/exception flows and state machines.
- The edge-case requirements in FR-INV, FR-SALE, FR-PAY, FR-SRET define the concurrency and exception scenarios to analyze.
- Assumptions A-001…A-040 and decisions DEC-001…DEC-010 constrain every design choice.
- The 48 open questions remain live; default handling must be visible in use cases where it matters.

---

*End of Phase 1 overview. Next: Phase 2 — System Analysis (`docs/02-system-analysis.md`).*
