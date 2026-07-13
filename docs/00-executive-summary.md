# Medicine Dealer ERP — Executive Summary

**Document ID:** DOC-EXE-001
**Version:** 1.0 (Phase 1 baseline)
**Audience:** Business owner, product team, engineering leads, QA, DevOps, stakeholders

---

## 1. What We Are Building

A centralized, multi-branch ERP for a medicine distributor/dealer that replaces manual stock registers, spreadsheets, and disconnected records with one system covering:

- Procurement: suppliers, purchases, batch receiving, purchase payments and returns, purchase bonus handling
- Inventory: batch-level stock, expiry/FEFO management, stock ledger, adjustments, write-offs
- Sales: invoicing to pharmacies/customers, cash and credit sales, partial payments, due collection, sales returns
- Field operations: doctors, doctor–medicine mapping, medical representative visits, territories
- Finance: customer receivables, supplier payables, cash/bank/MFS accounts, expenses, other income, gross and net profit
- Governance: roles and permissions, full audit trail, reports, settings

## 2. Why It Matters (Business Case)

The distributor's core economics depend on three things the current manual process cannot reliably control: **batch/expiry losses**, **receivables recovery**, and **true per-invoice profitability**. The ERP delivers:

| Business benefit | Mechanism |
|---|---|
| Lower expiry write-offs | FEFO batch enforcement, near-expiry alerts, expiry-blocked sales |
| Faster due recovery | Customer ledgers, aging, collection workflow, allocation control |
| Visible profit | Batch-actual costing, line-level margin, P&L reporting |
| Loss prevention | Role-based permissions, discount/cost controls, audit logs |
| Multi-branch control | Branch-isolated stock and finances with consolidated reporting |
| Field effectiveness | Doctor mapping, visit tracking, rep-wise sales reporting |

## 3. Scope at a Glance

- **MVP:** identity/roles/branches, catalog, batches, inventory, purchases (+bonus, payments, returns), customers, sales/invoices, partial payments & due collection, sales returns, doctors/visits/reps, expenses/income, cash-bank-MFS accounts, receivables/payables, P&L, reports, audit logs, settings, responsive web + PWA.
- **Phase 2:** inter-branch stock transfers, purchase/sales orders, barcode scanning, SMS/WhatsApp notifications, enhanced approval workflows, GPS/photo field visits, stock counting, representative commissions, price lists.
- **Future:** Flutter native app with offline-first field use, double-entry GL, forecasting/analytics, customer & supplier portals, thermal/POS printing, e-commerce ordering.
- **Out of scope:** manufacturing, HR/payroll, fleet management, statutory filing automation, multi-currency, multi-company.

## 4. Architecture at a Glance

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript, Tailwind + shadcn/ui, TanStack Query/Table, RHF + Zod, Zustand, PWA |
| Backend | Django + DRF, modular monolith, service layer owns business rules, API-first `/api/v1/` |
| Data | PostgreSQL (source of truth), append-only ledgers, derived balances, batch-actual costing |
| Async/Cache | Redis, Celery worker + beat (alerts, async reports, reconciliation) |
| Files | S3-compatible object storage via presigned uploads |
| Deployment | Cloud VM + Docker Compose + managed Postgres/Redis/S3, Nginx/Caddy edge |
| Mobile strategy | Responsive web + installable PWA first; Flutter app later |

## 5. Key Decisions Locked in Phase 1

| ID | Decision |
|---|---|
| DEC-001 | Bangladesh market: BDT, 15% VAT, July–June fiscal year, period locking |
| DEC-002 | MVP accounting = subledgers + cash/bank/MFS + P&L (no GL) |
| DEC-003 | Branch-isolated stock; transfers deferred to Phase 2 |
| DEC-004 | Cloud VM + Docker Compose + managed data services |
| DEC-005 | PWA: offline read shell + idempotent retry-safe writes; no offline write queue |
| DEC-007 | PostgreSQL source of truth; append-only ledgers; balances derived |
| DEC-008 | Costing: batch-specific actual cost, bonus allocated into effective unit cost |
| DEC-009 | FEFO mandatory with audited override |

## 6. Program Status

| Phase | Status |
|---|---|
| Phase 0 — Discovery/decisions | Complete |
| **Phase 1 — Requirements Analysis** | **Complete (this batch)** |
| Phase 2 — System Analysis | Next |
| Phases 3–13 | Planned (batched, gated) |

**Open business questions:** 48 tracked in `docs/open-questions.md`; each has a safe recommended default already reflected in the requirements. Client answers are requested before Sprint 3 (procurement) design freeze.

## 7. Primary Risks (see RISK register for full detail)

| ID | Risk | Mitigation |
|---|---|---|
| RISK-001 | Unanswered client questions cause late rework | Defaults implemented; answers gated before Sprint 3 |
| RISK-002 | Data migration quality (legacy Excel/paper) | Template-based import, dry runs, reconciliation (Phase 11) |
| RISK-003 | Concurrency errors on stock/payments | Row locking, DB constraints, idempotency keys, threaded tests |
| RISK-004 | Scope creep (transfers, commissions, GL pulled early) | Phase 2/3 backlog explicitly maintained |
| RISK-005 | Field staff adoption (mobile usability) | Mobile-first sale/collection flows, pilot branch, training |

## 8. How to Read This Documentation Set

| Need | Document |
|---|---|
| Requirements baseline | `docs/01-requirements-specification.md` + `docs/01-requirements/` |
| Decisions & assumptions | `docs/assumptions-log.md` |
| Client questionnaire | `docs/open-questions.md` |
| Traceability | `docs/22-requirements-traceability-matrix.md` |
| Later phases | `docs/02-...` through `docs/23-...` (produced per batch) |

---

*This summary is refreshed at every phase gate.*
