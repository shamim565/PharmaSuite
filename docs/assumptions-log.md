# Assumptions & Decisions Log

**Project:** Medicine Dealer ERP
**Document ID:** DOC-ASM-001
**Status:** Living document — updated at every phase gate
**Last updated:** Phase 1 (Requirements Analysis)
**Owner:** Solution Architect (maintained with Product Owner)

> **Purpose.** This log is the single source of truth for every decision and assumption that shapes the system. If a decision changes, the change is recorded here first, then propagated to affected documents using the traceability matrix (DOC-TRC-001). No document may contradict this log without an entry here.

---

## 1. ID Conventions

| Prefix | Meaning | Example |
|---|---|---|
| `DEC-###` | Locked decision (approved) | DEC-001 |
| `A-###` | Assumption (baseline is safe, but unconfirmed) | A-014 |
| `Q-###` | Open question awaiting client confirmation | Q-003 |
| `FR-<MOD>-###` | Functional requirement | FR-SALE-001 |
| `NFR-<CAT>-###` | Non-functional requirement | NFR-SEC-001 |
| `BR-<MOD>-###` | Business rule | BR-INV-001 |
| `UC-<MOD>-###` | Use case (Phase 2) | UC-SALE-001 |
| `DB-<MOD>-###` | Database entity (Phase 3) | DB-SALE-001 |
| `API-<MOD>-###` | API endpoint (Phase 5) | API-SALE-001 |
| `SCR-<MOD>-###` | UI screen (Phase 6) | SCR-SALE-001 |
| `TC-<MOD>-###` | Test case (Phase 9) | TC-SALE-001 |
| `RISK-###` | Risk register entry | RISK-007 |
| `ADR-###` | Architecture Decision Record | ADR-001 |

**Priority tags used in requirements:** `M` = MVP must-have, `S` = MVP should-have (stretch), `P2` = Phase 2, `FUT` = future/roadmap.

**Policy when assumptions are unconfirmed:** proceed with the documented default. If the client later disagrees, the change is handled through change control; the impact column below states the expected cost.

---

## 2. Locked Decisions

| ID | Decision | Rationale | Locked by | Impact if changed |
|---|---|---|---|---|
| DEC-001 | Market baseline: **Bangladesh** — currency BDT, VAT 15%, fiscal year **July–June**, monthly period locking | Confirmed by project owner (Batch A gate) | Owner | Tax/rounding/fiscal logic rework (~1 sprint) |
| DEC-002 | MVP accounting depth: **subledgers + cash/bank accounts + P&L**. No chart of accounts, no journals | Confirmed by project owner; fastest correct MVP; GL deferred | Owner | +4–6 weeks, new accounting module |
| DEC-003 | **Branches hold isolated stock**; inter-branch stock transfer deferred to Phase 2 | Confirmed by project owner | Owner | +2 weeks in Sprints 2–4, in-transit stock states |
| DEC-004 | Hosting: **cloud VM + Docker Compose + managed PostgreSQL/Redis/object storage**; Nginx/Caddy edge | Confirmed by project owner; low ops overhead at SMB scale | Owner | Infrastructure/runbook rework (Phase 10) |
| DEC-005 | PWA: **installable app + offline read shell + idempotent retry-safe writes**; no offline write queue in MVP | Confirmed by project owner; avoids stale-stock/ledger corruption | Owner | +3–4 weeks, conflict-resolution design |
| DEC-006 | Architecture style: **modular monolith**, API-first REST; Django + DRF backend; Next.js + TypeScript frontend | Mandated in the project brief | Client brief | Full re-architecture |
| DEC-007 | PostgreSQL is the **source of truth**; inventory/customer/supplier/financial ledgers are **append-only**; balances are derived and cached, never authoritative | Mandated in the brief; auditability and concurrency safety | Client brief | Data integrity exposure |
| DEC-008 | Costing model: **batch-specific actual cost**, with purchase bonus allocated into effective unit cost (`line net ÷ (qty + bonus qty)`) | Industry-correct, returns/COGS auditable; avoids weighted-average distortion | Architect (provisional until Phase 3 sign-off) | Costing/COGS/profit rework across sales & returns |
| DEC-009 | Stock batch selection: **FEFO mandatory**, permissioned audited override | Reduces expiry losses — core business benefit | Architect (provisional; Q-008) | Expiry-loss objective weakened |
| DEC-010 | All business rules are enforced **server-side**; UI restrictions are cosmetic only | Security/data integrity | Architect | — |

---

## 3. Assumptions

| ID | Assumption | Basis | Impact if wrong | Status |
|---|---|---|---|---|
| A-001 | Single legal entity (company) with multiple branches; no multi-company consolidation | Brief says "multi-branch", not multi-company | Company dimension + consolidation rework | Team baseline |
| A-002 | One physical warehouse/store per branch in MVP | SMB distributor scale | Warehouse entity + transfers pulled into MVP | Team baseline |
| A-003 | System is online-first; field users have intermittent but available connectivity | DEC-005 | Offline-first redesign | Team baseline |
| A-004 | Fiscal periods are locked monthly after close; Owner can override with audit | Common ERP control | Weak period control | Team baseline |
| A-005 | UI language English in MVP; copy is i18n-ready; Bangla added later | Pragmatic MVP | Bangla launch delay | Team baseline (Q-035) |
| A-006 | Server timestamps stored UTC; displayed Asia/Dhaka; business dates are local dates | Standard practice | Day-boundary report errors | Team baseline (Q-036) |
| A-007 | Money `NUMERIC(14,2)`; unit price/cost `NUMERIC(14,4)`; quantity `NUMERIC(14,3)`; **no floating point anywhere** | Financial correctness | Rounding/loss errors | Team baseline |
| A-008 | Auth: JWT access token (short-lived, memory) + rotating refresh token (httpOnly cookie), reuse detection, Argon2id hashing, optional TOTP 2FA for privileged roles | Industry standard for SPA + API | Auth redesign | Team baseline |
| A-009 | RBAC roles + granular permissions, plus branch-scoped object permissions | Brief requires roles/permissions + multi-branch | Permission model rework | Team baseline |
| A-010 | Soft delete for master data referenced by transactions; append-only ledgers; compensating reversals instead of deletes | DEC-007 | Audit/legal exposure | Team baseline |
| A-011 | A draft document does **not** reserve stock; availability is re-validated atomically at confirmation | Simplest correct concurrency model | Reservation table + expiry of reservations | Team baseline (Q-013) |
| A-012 | Purchase line = one batch (medicine + batch no. + expiry); sale line references exactly one batch | Batch traceability mandate | Multi-batch lines complicate ledgers | Team baseline |
| A-013 | Batch cost is immutable after confirmation; corrections only via adjustment | Auditability | Retroactive COGS changes | Team baseline |
| A-014 | Invoice/receipt numbers are allocated at confirmation inside the DB transaction; gapless per branch per fiscal year | Statutory expectation | Sequence gaps / renumbering | Team baseline (Q-022) |
| A-015 | Prices are VAT-exclusive by default; VAT added at line level; inclusive-pricing mode configurable per company | Common trade practice | Pricing display/compute changes | Team baseline (Q-020) |
| A-016 | Rounding: each line rounded half-up to 2dp; invoice-level round-off (±≤ 0.50 BDT) to nearest 1.00 BDT, shown as its own line | Statutory/trade practice | Minor reconciliation differences | Team baseline (Q-023) |
| A-017 | Walk-in (account-less) customers are disabled by default; a single "Walk-in" pseudo-customer can be enabled if required | Enables dues tracking, which is the core pain | Cash-sale workflow friction | Team baseline (Q-014) |
| A-018 | Price tiers: Retail, Wholesale, Custom per customer; no per-quantity break pricing in MVP | SMB reality | Quote/pricing engine work | Team baseline (Q-015) |
| A-019 | Doctor records are shared company-wide; doctor–rep assignments and visits are branch-scoped | MRs may cover multiple branches | Duplicate doctor records per branch | Team baseline |
| A-020 | Sales attribution: invoice stores `sales_rep_id`; medical influence stored as doctor reference on lines; commissions/incentives deferred to Phase 2 | Brief lists reps/visits but not commission rules | Payroll/commission module | Team baseline (Q-017) |
| A-021 | Doctor samples/promotional free goods are issued from a dedicated promotional stock movement and expensed as "Doctor Samples" | Prevents free-goods leakage | Sample tracking rework | Team baseline (Q-018) |
| A-022 | Cheque payments supported in MVP with lifecycle Pending → Cleared → Bounced; bounce reverses allocation | Common in the market | Workaround via manual reversals | Team baseline (Q-028) |
| A-023 | Audit logs retained 7 years, immutable from the application; financial documents retained indefinitely (soft-deleted) | Compliance/prudence | Retention policy rework | Team baseline (Q-043) |
| A-024 | Backups: nightly full + continuous WAL archiving, offsite copy; RPO ≤ 15 min, RTO ≤ 4 h | Industry baseline | Data-loss exposure | Team baseline |
| A-025 | Redis serves cache, Celery broker, and rate-limit counters; Celery worker + beat run in the same Docker host group | DEC-004 | Infra redesign | Team baseline |
| A-026 | Uploads (invoice images, attachments) go to S3-compatible storage via presigned URLs; 10 MB cap; MIME whitelist (pdf/jpg/png/webp) | Security + scalability | Local disk storage changes | Team baseline |
| A-027 | Reports exceeding ~2 s or ~10,000 rows are generated asynchronously by Celery and delivered via in-app notification/download link | Protects API latency targets | Timeouts under load | Team baseline |
| A-028 | Baseline scale: 100–200 concurrent users, ~1M ledger rows/year/branch; design must scale to 1,000 users without re-architecture | SMB distributor profile | Performance NFRs re-tuned | Team baseline |
| A-029 | Browser support: last 2 stable versions of Chrome, Edge, Safari, Firefox; current and previous iOS Safari and Android Chrome | Stated target devices | Extra QA matrix work | Team baseline |
| A-030 | API is versioned under `/api/v1/`; OpenAPI generated (drf-spectacular) and is the contract for frontend clients | API-first mandate | Client generation/contract drift | Team baseline |
| A-031 | List pagination is page-number based with `page_size ≤ 100`; cursor pagination only for ledger/audit streams | Fit for UI tables | Pagination rework | Team baseline |
| A-032 | `Idempotency-Key` header is required on all POSTs that create financial/inventory documents | Prevents duplicate submissions (mobile retries) | Duplicate payments/invoices risk | Team baseline |
| A-033 | No multi-currency in MVP; BDT only | DEC-001 context | FX module | Team baseline |
| A-034 | No manufacturing, HR/payroll, fixed assets, or fleet management modules | Out of scope per brief | Scope creep | Team baseline |
| A-035 | Statutory tax/regulatory filings (e.g., Mushak forms, DGDA submissions) are **not automated** in MVP; VAT-compliant invoice data fields and a VAT summary report are included | Legal counsel not engaged yet | Compliance gap | Team baseline (Q-020) |
| A-036 | Existing-business data is imported via documented templates + validators (Phase 11), with opening balances posted as `OPENING` ledger entries, never as fake documents | Clean audit trail | Unreliable opening balances | Team baseline |
| A-037 | Error responses use a standard envelope: `code`, `message`, `field_errors`, `request_id` (RFC 7807-inspired) | API-first consistency | Client error-handling rework | Team baseline |
| A-038 | All clinical/prescription data collected is the minimum required for the business; no diagnosis data stored | Privacy-by-default | Privacy exposure | Team baseline (Q-034) |
| A-039 | Mobile/PWA users primarily need: dashboard, sale entry, payment collection, visit logging, stock checks — not heavy admin screens | Usability strategy | UX rework | Team baseline |
| A-040 | The client provides invoice/letterhead formats, VAT registration details, and report samples before Sprint 4 | Assumes client engagement | Template/printing delays | Open — client dependency |

---

## 4. Decision Log (chronological)

| Date | ID | Event | By |
|---|---|---|---|
| Phase 0 | DEC-006..DEC-007 | Architecture/platform mandated in brief | Client |
| Phase 0 | DEC-001..DEC-005 | Batch A gate: market, accounting depth, transfers, hosting, offline strategy | Owner |
| Phase 1 | DEC-008..DEC-010 | Costing, FEFO, server-side enforcement baselines recorded (provisional) | Architect |

---

## 5. How to Change an Entry

1. Raise the proposed change against its `DEC-`/`A-` ID.
2. Assess impact using the traceability matrix (which FR/UC/DB/API/SCR/TC rows reference it).
3. Update this log with the new value, date, and approver.
4. Propagate to affected documents and bump their "Last updated" note.
5. If the change invalidates a signed-off phase artifact, that phase gate is re-opened.

---

*Next review: Phase 2 gate. Questions referenced above are maintained in `docs/open-questions.md`.*

| Date | ID | Decision | Status |
|---|---|---|---|
| Sprint 17 | DEC-011 | Purchase accounting stays subledger-only: supplier ledger carries payables; no AP accrual entry type (SRS excludes advanced GL). Financial-position reports subledger totals. | Approved |
| Sprint 17 | DEC-012 | Invoicing/records use browser print-to-PDF (A4 print views); no server-side PDF engine. | Approved |
| Sprint 17 | DEC-013 | Automated unit tests remain deferred; SRS DoD deviation recorded — verification via /tmp/smoke_s*.py + docs/uat-checklist.md | Approved |
