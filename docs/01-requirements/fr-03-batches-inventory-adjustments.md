# Functional Requirements — Batches, Inventory & Adjustments

**Document ID:** DOC-FR-03
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-BATCH — Batch & Expiry Management

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-BATCH-001 | Batches are created/updated at purchase confirmation; uniqueness is branch + medicine + batch number + expiry | Sys | M | Duplicate receipt into the same batch adds quantity, never a duplicate row |
| FR-BATCH-002 | Batch stores: batch number, manufacturing date, expiry date, supplier, purchase reference, received qty, bonus qty, effective unit cost | Sys/WM | M | All fields visible on batch detail; cost hidden without `VIEW_COST` |
| FR-BATCH-003 | Batch lifecycle status: active / quarantine / damaged / expired / depleted / recalled | Sys/WM | M | Status changes are audited; only active batches are saleable |
| FR-BATCH-004 | Expiry date mandatory for medicine items; validation: expiry > manufacturing date and not in the past at receipt (past-date receipt blocked unless `RECEIVE_EXPIRED` override) | WM | M | Invalid dates rejected at entry with field errors |
| FR-BATCH-005 | Batch effective cost is immutable after confirmation; corrections only via authorized stock adjustment | Sys | M | No API path mutates cost on a confirmed batch |
| FR-BATCH-006 | Batch quantity on hand is derived from the stock ledger; cached balance is rebuildable and reconciled nightly | Sys | M | Reconciliation job reports mismatches; cache rebuild is safe |
| FR-BATCH-007 | Full batch traceability: receipts, sales, returns, adjustments, write-offs with document links | Acct/WM | M | Trace report answers "where did this batch go" in one view |
| FR-BATCH-008 | Batch list with search/filter: medicine, batch number, expiry range, status, supplier, branch | All | M | Filters composable; results exportable |
| FR-BATCH-009 | Near-expiry list per threshold with days-to-expiry and stock value; feeds alerts | WM/BM | M | Matches expiry report totals |
| FR-BATCH-010 | Expired batches are unsellable; system blocks selection with `BATCH_EXPIRED` | Sys | M | Attempt to sell expired batch fails and is logged |
| FR-BATCH-011 | Quarantine/damaged stock is segregated, non-saleable, and reportable | WM | M | Quarantine quantity never included in available stock |
| FR-BATCH-012 | Batch recall: mark recalled, block sales, produce impact report (customers who received the batch) | WM/QA | S | Recall report lists invoices and quantities per customer |
| FR-BATCH-013 | Show MRP vs selling price on batch/sale screens; warn if selling price exceeds MRP (configurable block) | SO | S | Warning shown; override recorded if permitted |
| FR-BATCH-014 | Manual batch creation allowed only for opening imports (Phase 11) and authorized adjustments | Sys | M | Manual create path permission-gated and audited |
| FR-BATCH-015 | Correct a data-entry expiry date before any movement, with permission and audit; blocked once the batch has movements (use adjustment path instead) | WM/Adm | M | Edit recorded with before/after; blocked case returns clear error |

## FR-INV — Inventory & Stock Ledger

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-INV-001 | Maintain an append-only stock ledger; movement types: purchase, sale, sales return, purchase return, adjustment up/down, expiry write-off, damage write-off, promotional issue, opening, transfer (P2) | Sys | M | No update/delete paths exist; corrections are new entries |
| FR-INV-002 | Every movement references its source document, actor, branch, medicine, batch, quantity (base units), unit cost, and timestamp | Sys | M | Movement detail view shows full context |
| FR-INV-003 | Real-time stock balance per branch + medicine + batch (cached, derived from ledger, transactionally updated) | Sys | M | Balance always equals ledger sum after each committed transaction |
| FR-INV-004 | Aggregate stock per medicine per branch across batches, with batch drill-down | All | M | Aggregates reconcile with batch detail |
| FR-INV-005 | FEFO auto-selection of saleable batches (earliest expiry, then earliest receipt) on sale and other outbound screens | Sys | M | Preselected batches follow FEFO; ordering deterministic |
| FR-INV-006 | Manual batch override requires `INV_OVERRIDE_FEFO` plus reason code; override rate reported | SO/BM | M | Overrides audited and visible in a report |
| FR-INV-007 | Atomic availability validation and deduction at document confirmation | Sys | M | A sale either fully succeeds or fully rolls back |
| FR-INV-008 | Negative stock impossible; failure returns `INSUFFICIENT_STOCK` with per-batch shortage details | Sys | M | DB constraint and service check both enforce |
| FR-INV-009 | Concurrent outbound operations serialize safely via row locks in deterministic key order with bounded retry | Sys | M | Threaded concurrency tests cannot oversell (TC-INV-…, Phase 9) |
| FR-INV-010 | Low-stock detection against per-branch reorder levels; feeds dashboard and alerts | Sys | M | Items at/below reorder level appear in report and notifications |
| FR-INV-011 | Stock valuation at batch actual cost, per branch and consolidated | Acct/BM | M | Valuation equals Σ(batch qty × batch cost) |
| FR-INV-012 | Expiry position reports: near-expiry, expired, by value and quantity, filterable by branch/category | WM/BM | M | Totals reconcile with batch data |
| FR-INV-013 | Movement history per medicine/batch with date-range and type filters | All | M | Export to Excel/CSV available |
| FR-INV-014 | Stock summary grouped by category, manufacturer, generic | BM/Adm | M | Totals reconcile with valuation |
| FR-INV-015 | Slow-moving / non-moving analysis over a configurable window (default 90 days) | BM | S | Items with zero sales in window listed with stock value |
| FR-INV-016 | Dead-stock report (no sales in configurable period, e.g., 180 days) | BM | S | Report highlights action candidates |
| FR-INV-017 | Batch-wise on-hand detail with expiry countdown and value | WM | M | Drill-down from any stock report |
| FR-INV-018 | Live stock availability shown in sale entry per medicine and per candidate batch | SO | M | Stale data refresh policy defined; server re-validates at confirm |
| FR-INV-019 | Cost figures masked for roles lacking `VIEW_COST` at API level | Sys | M | API tests assert masking |
| FR-INV-020 | Nightly reconciliation compares cached balances with ledger sums; discrepancies raise alerts and a repair task | Sys | M | Alert includes branch/medicine/batch and delta |
| FR-INV-021 | All stock-affecting POSTs accept `Idempotency-Key`; replays return the original result | Sys | M | Duplicate confirm returns same document, no double movement |
| FR-INV-022 | Conversions: all ledger quantities are base units; display may use friendly units without changing stored values | Sys | M | Round-trip conversion tests pass |
| FR-INV-023 | Draft documents do **not** reserve stock; confirmation is the sole commitment point | Sys | M | Creating drafts never affects availability |
| FR-INV-024 | Promotional stock pool: quantities reserved for doctor samples tracked separately and non-saleable | WM/MR | M | Promo balance visible; promo issues reduce only promo stock |
| FR-INV-025 | Export any stock view to Excel/CSV/PDF with applied filters | All | M | Export matches on-screen filters and totals |

## FR-ADJ — Stock Adjustments, Write-offs & Damage

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-ADJ-001 | Adjustment document (increase/decrease) with mandatory reason codes: data correction, physical count variance, damage, expiry write-off, found stock, promotional issue, recall disposal | WM/BM | M | Reason required; list configurable per company |
| FR-ADJ-002 | Adjustment targets a specific branch + medicine + batch with quantity and cost impact | WM | M | Batch must exist; quantity non-zero |
| FR-ADJ-003 | Adjustments above the role threshold require approval before posting | BM/Adm | M | Pending approval state; approver cannot be requester (dual-control) |
| FR-ADJ-004 | Posted adjustments write ledger entries; write-off types also post an expense to the configured expense category/account | Sys | M | Accounts receivable/expense effects visible in reports |
| FR-ADJ-005 | Decrease adjustments cannot drive a batch below zero effective stock | Sys | M | Validation blocks with available quantity shown |
| FR-ADJ-006 | Attachment support (photo/evidence) with type/size validation | WM | S | Stored in object storage via presigned upload |
| FR-ADJ-007 | Reversal of a posted adjustment via compensating entry with permission and mandatory reason; period lock applies | BM/Adm | M | Original remains; reversal is linked and audited |
| FR-ADJ-008 | Period locking enforced: no postings into locked fiscal months except Owner `PERIOD_OVERRIDE` (audited) | Sys | M | Attempt returns `PERIOD_LOCKED` |
| FR-ADJ-009 | Adjustment register report: date range, reason, branch, product, user, value | Acct/BM | M | Exportable; totals reconcile |
| FR-ADJ-010 | Supports Phase 2 physical count variance posting (count session → variance → adjustment) | WM | P2 | Not scheduled |

---

*Cross-references: BR-INV-001…011, BR-BATCH-001…004 in `docs/01-requirements/08-business-rules.md`; concurrency edge cases analyzed in Phase 2.*
