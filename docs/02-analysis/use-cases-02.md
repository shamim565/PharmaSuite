# Use Cases — Part 2: Sales, CRM, Finance, Platform

**Document ID:** DOC-UC-02
**Parent:** `docs/02-system-analysis.md`
**Format per UC:** Actor · Priority · Related FRs · Preconditions · Trigger · Main flow · Alternative flows (A#) · Exception flows (E#) · Postconditions · Notes

---

## UC-CUST-001 — Manage Customer
**Actor:** SO/Adm · **Pri:** M · **FRs:** FR-CUST-001…014
- **Preconditions:** `CUSTOMER_MANAGE`.
- **Trigger:** New/edit customer.
- **Main flow:** 1) Enter identity (code unique), type, contacts, address/area → 2) credit limit + credit days → 3) price tier + assigned sales rep → 4) save → 5) customer selectable on invoices.
- **E1:** Duplicate code → rejected; duplicate name/phone → warning + confirm.
- **Postconditions:** Customer active; audited.

## UC-CUST-002 — View Customer Ledger/Aging
**Actor:** Acct/SO · **Pri:** M · **FRs:** FR-CUST-005…007, FR-PAY-016
- **Preconditions:** `CUSTOMER_VIEW`.
- **Trigger:** Open ledger from customer or due list.
- **Main flow:** 1) Show append-only entries (opening, invoices, payments, returns, adjustments) → 2) date-range statement with opening/closing → 3) aging buckets with drill-down → 4) export/print → 5) "collect" action pre-fills collection (UC-PAY-004).
- **Postconditions:** Read-only; totals reconcile with ledgers.

## UC-CUST-003 — Set Credit Terms / Credit Hold
**Actor:** Adm/Acct · **Pri:** M · **FRs:** FR-CUST-002,017
- **Preconditions:** `CREDIT_MANAGE`.
- **Trigger:** Credit review.
- **Main flow:** 1) Update limit/days or set credit hold → 2) future credit sales obey new rules → 3) hold blocks new credit invoices with `CUSTOMER_ON_HOLD` → 4) release via authorized role.
- **Postconditions:** Credit controls active; audited.

## UC-SALE-001 — Create Draft Sale
**Actor:** SO · **Pri:** M · **FRs:** FR-SALE-001…008,011…014,027…035
- **Preconditions:** Customer, medicines, saleable batches exist; `SALE_CREATE`.
- **Trigger:** "New sale".
- **Main flow:** 1) Select customer (search) → 2) branch context, date, sales rep default → 3) add lines: search medicine → FEFO batches proposed → qty (sale unit) → tier price → line discount → VAT → 4) optional doctor reference per line → 5) invoice-level discount/round-off → 6) delivery info/notes → 7) save draft (no stock effect) or proceed to confirm.
- **A1:** Copy previous invoice lines (FR-SALE-031).
- **A2:** Scheme suggestion adds zero-price bonus line (FR-SALE-034).
- **E1:** Qty > available → inline block with shortage.
- **E2:** Rx-required item without reference → warn/require per policy.
- **Postconditions:** Draft editable by creator/branch; audited.

## UC-SALE-002 — Confirm Sale
**Actor:** SO/System · **Pri:** M · **FRs:** FR-SALE-015…017,025,026,038, BR-SALE-001…010
- **Preconditions:** Draft valid; customer active; credit checks pass (or override); batch availability re-validated.
- **Trigger:** Confirm action.
- **Main flow:** 1) Revalidate lines, prices, availability → 2) begin transaction → 3) lock batch rows (deterministic order) → 4) deduct stock (FEFO batches, base units) → 5) allocate invoice number → 6) post stock ledger entries → 7) post customer ledger receivable (grand total) → 8) post account transaction for paid-at-entry amount → 9) set invoice states (lifecycle/payment/return/fulfillment) → 10) commit → 11) show invoice for print/share.
- **E1:** Insufficient stock after lock → `INSUFFICIENT_STOCK` rollback; draft preserved.
- **E2:** Credit limit/overdue violation → block with override path (UC-SALE-003).
- **E3:** Duplicate submit (double-tap/retry) → idempotency returns existing invoice.
- **Postconditions:** Invoice CONFIRMED; stock/ledger/accounts consistent; audited.
- **Notes:** BR-SALE-003/004; concurrency tests TC-CONC-001.

## UC-SALE-003 — Override Below-Cost/Credit Controls
**Actor:** BM/Owner · **Pri:** M · **FRs:** FR-SALE-005,009,030, BR-SALE-005/006, BR-AUD-003
- **Preconditions:** Confirmation blocked by credit limit, overdue rule, margin floor, or below-cost guard; actor holds the override permission.
- **Trigger:** Override request.
- **Main flow:** 1) System shows exact violation and required permission → 2) actor enters reason code/note → 3) override recorded on invoice metadata → 4) confirmation proceeds (UC-SALE-002) → 5) exception appears in FR-RPT-024.
- **E1:** Actor lacks permission → blocked; escalation path suggested.
- **Postconditions:** Sale completed with full audit; exception reportable.

## UC-SALE-004 — Cancel Invoice
**Actor:** Adm · **Pri:** M · **FRs:** FR-SALE-018,019, BR-SALE-008/009
- **Preconditions:** Invoice CONFIRMED with no payments and no returns; period open.
- **Trigger:** Cancellation decision (wrong customer/items).
- **Main flow:** 1) System validates no payments/returns → 2) cancel posts reversal: restock to original batches, reverse customer ledger, reverse any account transaction, mark VOID (number retained) → 3) reason recorded → 4) audited.
- **E1:** Payments exist → blocked; use sales return/credit note.
- **E2:** Returns exist → blocked; complete return path instead.
- **E3:** Period locked → Owner override only.
- **Postconditions:** Fully reversed effects; original visible as VOID.

## UC-SALE-005 — Reprint/Share Invoice
**Actor:** SO · **Pri:** M · **FRs:** FR-SALE-020,021,022
- **Preconditions:** Confirmed invoice.
- **Trigger:** Reprint/share action.
- **Main flow:** 1) Render server-side PDF from stored data + template → 2) first print plain; reprint adds REPRINT watermark → 3) share via native share (mobile) or download link → 4) reprint count audited.
- **E1:** Template/logo missing → fall back to default template with warning.
- **Postconditions:** PDF matches stored invoice exactly.

## UC-SALE-006 — Sale with Payment at Entry
**Actor:** SO/Acct · **Pri:** M · **FRs:** FR-SALE-010, FR-PAY-001…007
- **Preconditions:** Same as UC-SALE-002; collection permission if taking money.
- **Trigger:** Customer pays (fully/partially) at sale time.
- **Main flow:** 1) At confirm, enter payment amount and method(s) with account mapping → 2) receipt number allocated → 3) confirm transaction posts invoice + payment + allocation atomically → 4) receipt printed/shared with invoice.
- **E1:** Payment > invoice total → block unless advance recorded (Q-026).
- **E2:** Method account insufficient → `INSUFFICIENT_FUNDS`.
- **Postconditions:** Invoice paid/partially paid; receipt issued; ledgers consistent.

## UC-PAY-001 — Collect Payment (FIFO Allocation)
**Actor:** Acct/SO · **Pri:** M · **FRs:** FR-PAY-001…007,017, BR-PAY-001…008
- **Preconditions:** Customer with outstanding invoices; `PAYMENT_COLLECT`.
- **Trigger:** Customer pays.
- **Main flow:** 1) Select customer → system shows open invoices and total due → 2) enter amount, date, method(s), accounts, reference, collector → 3) system proposes FIFO allocation (oldest invoice date first) → 4) user may re-allocate manually → 5) validate Σ ≤ amount and per-invoice ≤ outstanding → 6) post payment + allocations + account transaction atomically with row locks → 7) update invoice payment states → 8) print/share receipt.
- **A1:** Additional amount → customer advance (BR-PAY-007).
- **E1:** Concurrent allocation on same invoice → row lock serializes; second request sees updated outstanding.
- **E2:** Duplicate submit → idempotency returns original receipt.
- **Postconditions:** Dues reduced; receipt numbered; audited.

## UC-PAY-002 — Apply Partial Payment
**Actor:** System · **Pri:** M · **FRs:** FR-PAY-004, FR-SALE-025
- **Preconditions:** Allocation < invoice outstanding.
- **Trigger:** Payment posting (any amount).
- **Main flow:** 1) Invoice outstanding recomputed → 2) payment status → PARTIALLY_PAID → 3) due list/aging reflects remainder → 4) strike rate unchanged; no other side effects.
- **Postconditions:** Outstanding = grand total − allocated.
- **Notes:** BR-PAY-002.

## UC-PAY-003 — Reverse Payment
**Actor:** Acct/Owner · **Pri:** M · **FRs:** FR-PAY-009, BR-PAY-001/004
- **Preconditions:** Payment exists; permission per period rule.
- **Trigger:** Bounced cheque, wrong entry, refund path.
- **Main flow:** 1) Reason entered → 2) reversal posts: reverse account transaction, reverse allocations, restore invoice states, restore customer ledger → 3) linked to original; cross-period flagged → 4) audited.
- **E1:** Cross-period → Owner only.
- **Postconditions:** Balances restored; audit chain intact.

## UC-PAY-004 — Collect Old Due from Due List
**Actor:** Acct/SO · **Pri:** M · **FRs:** FR-PAY-016, FR-CUST-007
- **Preconditions:** Aging/due report available.
- **Trigger:** Collection round.
- **Main flow:** 1) Open due list (customer/invoice/aging) → 2) filter by rep/area/overdue bucket → 3) quick-collect opens pre-filled collection sheet → 4) executes UC-PAY-001 → 5) due list refreshes.
- **Postconditions:** Targeted recovery; collector attribution recorded.

## UC-PAY-005 — Customer Cheque Lifecycle
**Actor:** Acct · **Pri:** S · **FRs:** FR-PAY-013
- **Preconditions:** Method = cheque.
- **Trigger:** Cheque deposit/clearing.
- **Main flow:** 1) Payment recorded Pending → 2) mark Cleared (allocation stands) or Bounced → 3) bounce triggers reversal (UC-PAY-003), invoices re-open → 4) cheque register updated.
- **Postconditions:** Cheque status accurate; audited.

## UC-PAY-006 — Apply Customer Advance
**Actor:** Acct/System · **Pri:** S · **FRs:** FR-PAY-005,018, BR-PAY-006/007
- **Preconditions:** Customer has advance balance; invoice outstanding exists.
- **Trigger:** Auto-apply at confirmation (if enabled) or manual apply.
- **Main flow:** 1) System shows available advance → 2) allocates to invoice(s) → 3) invoice states update → 4) advance balance decreases → 5) audited.
- **Postconditions:** Advance applied; no cash movement.

## UC-SRET-001 — Process Sales Return (Restock/Quarantine)
**Actor:** SO/WM · **Pri:** M · **FRs:** FR-SRET-001…005,010,016, BR-SRET-001…005
- **Preconditions:** Original confirmed invoice; returnable quantity > 0.
- **Trigger:** Customer return.
- **Main flow:** 1) Open invoice → create return → 2) select lines/quantities ≤ sold − returned → 3) reason + per-line condition (resellable/damaged/expired) → 4) system computes credit amount with VAT/discount reversal at original costs → 5) if resellable/non-expired → restock original batch; else quarantine pool → 6) confirm atomically: stock movements, customer ledger credit, invoice return status → 7) credit note numbered/printable.
- **E1:** Over-return → blocked with remaining quantity.
- **E2:** Period locked → `PERIOD_LOCKED` unless override.
- **Postconditions:** Stock and receivable effects posted; audit intact.
- **Notes:** Bonus/free goods returned per BR-SRET-008.

## UC-SRET-002 — Refund via Credit Note
**Actor:** Acct · **Pri:** M · **FRs:** FR-SRET-005,006, BR-SRET-004
- **Preconditions:** Confirmed return exists; refund decision.
- **Trigger:** Customer requests money back / dues adjustment.
- **Main flow:** 1) Select refund method: customer credit (default) / cash / bank / adjust dues → 2) cash/bank requires `RETURN_REFUND` and posts account transaction → 3) credit note finalized and shared → 4) customer ledger reflects method.
- **Postconditions:** Refund recorded per method; audited.

## UC-SRET-003 — No-Invoice Return (Exception)
**Actor:** Adm · **Pri:** S · **FRs:** FR-SRET-008, BR-SRET-006
- **Preconditions:** `SRET_NO_INVOICE` permission (default off).
- **Trigger:** Return without traceable invoice (lost invoice, bulk deal).
- **Main flow:** 1) Actor confirms permission and enters reason → 2) selects batch/medicine and quantity → 3) condition decides restock/quarantine → 4) standalone credit note created → 5) flagged in Exception Report.
- **E1:** Permission missing → blocked.
- **Postconditions:** Return recorded with elevated audit visibility.

## UC-DOC-001 — Manage Doctor
**Actor:** MR/Adm · **Pri:** M · **FRs:** FR-DOC-001…006,010,014
- **Preconditions:** `DOCTOR_MANAGE`.
- **Trigger:** New doctor/update.
- **Main flow:** 1) Enter profile (name, specialty, degrees, contacts, registration no.) → 2) chambers/affiliations → 3) category A/B/C, potential, territory → 4) assign responsible MR(s) → 5) save; visible in visit planning and mapping.
- **E1:** Duplicate registration → rejected; duplicate warning on name/phone.
- **Postconditions:** Doctor active; audited.

## UC-DOC-002 — Map Medicines to Doctor
**Actor:** MR/BM · **Pri:** M · **FRs:** FR-DOC-007…009
- **Preconditions:** Doctor + medicines exist.
- **Trigger:** Promotion planning.
- **Main flow:** 1) Open doctor → add medicines (with strength/priority notes) → 2) effective dates → 3) save → 4) mapping visible to MR in visit log and printable list → 5) history retained for past-period reports.
- **Postconditions:** Mapping active; report attribution unchanged for past periods (BR-CRM-005).

## UC-DOC-003 — View Doctor Attributed Sales
**Actor:** BM/Adm · **Pri:** M · **FRs:** FR-DOC-012
- **Preconditions:** Invoices have doctor references.
- **Trigger:** ROI review.
- **Main flow:** 1) Open doctor report → 2) filter by period/medicine/branch → 3) show invoiced value/quantity attributed → 4) drill-down to invoices.
- **Postconditions:** Read-only; permission-gated if value includes cost/margin.

## UC-DVIS-001 — Log Visit with Samples
**Actor:** MR · **Pri:** M · **FRs:** FR-DVIS-001,002,003,009, BR-CRM-002/004
- **Preconditions:** Doctor assigned to MR; promo stock available for samples.
- **Trigger:** Post-visit logging (mobile).
- **Main flow:** 1) Select planned visit or ad-hoc doctor → 2) capture date/time, products discussed (from mapping), outcome/interest → 3) add samples (medicine, batch, qty) → 4) system deducts PROMO stock and records per doctor → 5) next visit date/notes → 6) save; editable within window per policy.
- **E1:** Insufficient promo stock → blocked with available qty (no fallback to saleable stock).
- **E2:** Doctor not assigned to this MR → warn/block per policy.
- **Postconditions:** Visit + samples recorded; stock promo balance updated; audited.

## UC-DVIS-002 — Plan Visits
**Actor:** MR/BM · **Pri:** M · **FRs:** FR-DVIS-001,010, FR-DOC-019
- **Preconditions:** Doctors/territories exist.
- **Trigger:** Weekly planning.
- **Main flow:** 1) Create planned visits (doctor, date, purpose, priority) → 2) assign to MR → 3) calendar/agenda view → 4) reminders generated (day before) → 5) completion links to UC-DVIS-001 or marks missed with reason.
- **Postconditions:** Plan visible; coverage report uses plan vs actual.

## UC-DVIS-003 — View Coverage Report
**Actor:** BM · **Pri:** M · **FRs:** FR-DVIS-005,006,007
- **Preconditions:** Visits and plans exist.
- **Trigger:** Performance review.
- **Main flow:** 1) Select period/MR/territory → 2) planned vs actual, visit frequency per doctor, missed reasons, samples issued → 3) export.
- **Postconditions:** Read-only; matches visit entries.

## UC-REP-001 — View Rep Performance
**Actor:** BM · **Pri:** M · **FRs:** FR-REP-008…010,014
- **Preconditions:** Sales/payments/visits exist for the period.
- **Trigger:** Performance review.
- **Main flow:** 1) Select rep and period → 2) sales value/qty (invoice attribution), collections, visit coverage → 3) target vs achievement where targets set → 4) ranking view → 5) export.
- **Postconditions:** Read-only; same filters as source reports.

## UC-REP-002 — Assign Customers/Doctors/Territories
**Actor:** BM · **Pri:** M · **FRs:** FR-REP-003,004,005,011
- **Preconditions:** Rep exists.
- **Trigger:** Coverage change.
- **Main flow:** 1) Choose rep → 2) assign customers (SR) and/or doctors (MR), territory, effective dates → 3) save; historical assignments retained → 4) defaults update on new invoices/visits.
- **E1:** Deactivating rep → reassignment guard lists active assignments (FR-REP-015).
- **Postconditions:** Assignments effective-dated; audited.

## UC-REP-003 — Set Targets
**Actor:** BM/Owner · **Pri:** S · **FRs:** FR-REP-006,007
- **Preconditions:** Rep exists; period open.
- **Trigger:** Monthly planning.
- **Main flow:** 1) Select rep + period → 2) enter sales value/qty and/or visit-count targets → 3) save (editable while period open, audited) → 4) achievement reports use targets.
- **Postconditions:** Targets active; past periods unchanged.

## UC-TER-001 — Manage Territories
**Actor:** BM/Adm · **Pri:** M · **FRs:** FR-TER-001…005
- **Preconditions:** `TERRITORY_MANAGE`.
- **Trigger:** Coverage structure change.
- **Main flow:** 1) Create/edit hierarchy region→area→territory → 2) assign customers/doctors → 3) reports roll up → 4) reassignment history retained.
- **E1:** Cycle in hierarchy → rejected.
- **E2:** Deactivate with active assignments → blocked with list.
- **Postconditions:** Territory structure current; audited.

## UC-EXP-001 — Record Expense
**Actor:** Acct · **Pri:** M · **FRs:** FR-EXP-001,002,004,008
- **Preconditions:** Category exists; `EXPENSE_POST`.
- **Trigger:** Expense incurred.
- **Main flow:** 1) Enter date, branch, category, amount, payment account, payee, reference → 2) attach bill (optional) → 3) below threshold → post immediately: account transaction + P&L; above → PENDING_APPROVAL (UC-EXP-002).
- **E1:** Account insufficient → `INSUFFICIENT_FUNDS` when posting.
- **E2:** Locked period → blocked/override path.
- **Postconditions:** Expense posted or pending; audited.

## UC-EXP-002 — Approve/Reject Expense
**Actor:** BM/Adm · **Pri:** M · **FRs:** FR-EXP-003
- **Preconditions:** Expense pending above threshold.
- **Trigger:** Approval queue review.
- **Main flow:** 1) Review detail/attachment → 2) approve → posts (UC-EXP-001 step 3) or reject with reason → 3) requester notified.
- **E1:** Approver = requester → blocked (dual control).
- **Postconditions:** POSTED/REJECTED; audited.

## UC-EXP-003 — Reverse Expense
**Actor:** Acct/Owner · **Pri:** M · **FRs:** FR-EXP-005
- **Preconditions:** Expense posted; permission per period.
- **Trigger:** Error or refund.
- **Main flow:** 1) Reason → 2) compensating entry reverses account + P&L effect → 3) linked; cross-period flagged → 4) audited.
- **Postconditions:** Balances restored.

## UC-INC-001 — Record Other Income
**Actor:** Acct · **Pri:** M · **FRs:** FR-INC-001…003
- **Preconditions:** Category exists; `INCOME_POST`.
- **Trigger:** Income received.
- **Main flow:** 1) Enter date, branch, category, amount, account, payer/reference → 2) post immediately (account + P&L) → 3) receipt/voucher printable.
- **Postconditions:** Income recorded; audited.

## UC-INC-002 — Reverse Income
**Actor:** Acct/Owner · **Pri:** M · **FRs:** FR-INC-004
- **Preconditions:** Income posted.
- **Trigger:** Error discovered.
- **Main flow:** 1) Reason → 2) compensating reversal → 3) linked/audited.
- **Postconditions:** Balances restored.

## UC-FIN-001 — View Profit Reports
**Actor:** Owner/BM · **Pri:** M · **FRs:** FR-FIN-013,014,027, FR-RPT-027
- **Preconditions:** `VIEW_PROFIT`.
- **Trigger:** Profit review.
- **Main flow:** 1) Select period/branch → 2) gross profit (revenue − COGS) by item/category/invoice → 3) net profit (gross − expenses + income) with comparison columns → 4) drill-down → 5) export.
- **Postconditions:** Numbers reconcile with ledgers and sales/purchase registers.
- **Notes:** BR-FIN-003.

## UC-FIN-002 — Lock/Unlock Fiscal Period
**Actor:** Owner · **Pri:** M · **FRs:** FR-FIN-021, BR-DOC-004
- **Preconditions:** Month-end checks complete (UC-FIN-007); `PERIOD_LOCK`.
- **Trigger:** Month close.
- **Main flow:** 1) System runs close checklist (pending approvals, unposted items, reconciliation status) → 2) warnings listed → 3) Owner locks period → 4) postings into the period blocked → 5) unlock only by Owner with reason; audited.
- **E1:** Unresolved checklist items → warning (lock allowed with acknowledgment).
- **Postconditions:** Period state enforced everywhere.

## UC-FIN-003 — Transfer Between Accounts
**Actor:** Acct · **Pri:** M · **FRs:** FR-FIN-005,009
- **Preconditions:** Two accounts, sufficient source balance (per policy).
- **Trigger:** Fund movement (bank deposit, cash to bank).
- **Main flow:** 1) Select source/destination, amount, date, reference → 2) validate balance rules → 3) post linked pair atomically with shared transfer id → 4) vouchers printable.
- **E1:** Insufficient source (no negative allowed) → blocked.
- **Postconditions:** Balances updated; audited.

## UC-FIN-004 — Reconcile Ledgers
**Actor:** System/Acct · **Pri:** M · **FRs:** FR-FIN-020, NFR-REL-003
- **Preconditions:** Nightly/manual trigger.
- **Trigger:** Schedule or discrepancy suspicion.
- **Main flow:** 1) Compare cached balances vs ledger sums for customers, suppliers, accounts, stock → 2) list discrepancies with deltas → 3) repair tasks recompute caches with audit → 4) alert if mismatch persists.
- **Postconditions:** Integrity verified/repaired; report available.

## UC-FIN-005 — Post Deposit/Withdrawal
**Actor:** Acct · **Pri:** M · **FRs:** FR-FIN-004
- **Preconditions:** Account exists; `ACCOUNT_ADJUST`.
- **Trigger:** Owner capital, bank charges, cash correction.
- **Main flow:** 1) Choose type, amount, date, reason → 2) validate balance policy → 3) post account transaction → 4) audited.
- **Postconditions:** Account balance updated.

## UC-FIN-006 — View AR/AP Aging
**Actor:** Acct · **Pri:** M · **FRs:** FR-FIN-011,012
- **Preconditions:** `RECEIVABLE_VIEW`/`PAYABLE_VIEW`.
- **Trigger:** Collection/payment planning.
- **Main flow:** 1) Choose AR or AP → 2) filter branch/supplier/customer/rep → 3) buckets current/1-30/31-60/61-90/90+ → 4) drill to invoices → 5) export.
- **Postconditions:** Totals match ledgers.

## UC-FIN-007 — Month-End Close Pack
**Actor:** Acct/Owner · **Pri:** M · **FRs:** FR-FIN-017…021,027, FR-RPT-027,028
- **Preconditions:** Period activity complete enough to report.
- **Trigger:** Month end.
- **Main flow:** 1) Run checklist: pending approvals, reconciliation status, unallocated payments, pending pickups → 2) generate pack: sales/purchase registers, VAT output/input/net, stock valuation, AR/AP aging, P&L, exception summary → 3) review with Owner → 4) lock period (UC-FIN-002) → 5) archive pack to exports/S3.
- **E1:** Material discrepancies → fix before lock.
- **Postconditions:** Close pack archived; period locked.

## UC-RPT-001 — Generate/Export Report
**Actor:** All · **Pri:** M · **FRs:** FR-RPT-001…030, NFR-PERF-003
- **Preconditions:** `REPORT_VIEW` (+ cost/profit for sensitive reports).
- **Trigger:** Report request.
- **Main flow:** 1) Select report → 2) filters (branch/date/others) → 3) server executes query with permission-aware columns → 4) view/paginate → 5) export Excel/PDF/CSV → 6) export audited when sensitive.
- **E1:** Est. > threshold → async job (UC-RPT-003).
- **Postconditions:** Numbers match source documents.

## UC-RPT-002 — View Exception Report
**Actor:** Owner · **Pri:** M · **FRs:** FR-RPT-024, BR-AUD-003
- **Preconditions:** Overrides/exceptions recorded.
- **Trigger:** Control review.
- **Main flow:** 1) Select period/branch/type (below-cost, credit override, FEFO override, no-invoice return, free goods, duplicate-invoice override, write-offs) → 2) list with links to documents and actors → 3) drill-down → 4) export.
- **Postconditions:** Every override is visible to the Owner.

## UC-RPT-003 — Generate Large Report Asynchronously
**Actor:** System · **Pri:** S · **FRs:** FR-RPT-030, A-027
- **Preconditions:** Report exceeds interactive threshold.
- **Trigger:** User requests heavy report.
- **Main flow:** 1) API accepts request → 2) Celery job generates file → 3) in-app notification with download link (expiring) → 4) user downloads.
- **E1:** Job failure → notification with retry action; error logged/alerted.
- **Postconditions:** File stored in object storage with expiry; job audited.

## UC-NOTIF-001 — Receive Alerts
**Actor:** All · **Pri:** M · **FRs:** FR-NOTIF-001…007
- **Preconditions:** Relevant events occur (thresholds, overdue, approvals, visits).
- **Trigger:** Event or scheduled digest.
- **Main flow:** 1) System generates notifications per subscription rules → 2) in-app center shows unread count → 3) deep link opens filtered view → 4) mark read/all.
- **E1:** Channel delivery failure (email/SMS) → logged; in-app remains authoritative.
- **Postconditions:** Alerts delivered; delivery logged.

## UC-NOTIF-002 — Manage Notification Preferences
**Actor:** All · **Pri:** M · **FRs:** FR-NOTIF-008…012
- **Preconditions:** Authenticated.
- **Trigger:** Preference change.
- **Main flow:** 1) Toggle per-type channels → 2) critical alerts remain locked on → 3) save.
- **Postconditions:** Preferences applied to future notifications.

## UC-AUD-001 — Review Audit Log
**Actor:** Owner/SA · **Pri:** M · **FRs:** FR-AUD-001…006,009
- **Preconditions:** `AUDIT_VIEW`.
- **Trigger:** Investigation/compliance.
- **Main flow:** 1) Filter by entity/actor/action/date/branch → 2) view before/after snapshots → 3) document timeline view → 4) 403 for unauthorized roles.
- **Postconditions:** Read-only; access itself logged.

## UC-AUD-002 — Export Audit Extract
**Actor:** Owner · **Pri:** S · **FRs:** FR-AUD-007,008
- **Preconditions:** `AUDIT_EXPORT`.
- **Trigger:** External audit request.
- **Main flow:** 1) Choose filters → 2) export CSV with hash manifest → 3) export event audited.
- **Postconditions:** Tamper-evident extract delivered.

## UC-SET-001 — Configure Numbering Series
**Actor:** Owner · **Pri:** M · **FRs:** FR-SET-005, BR-DOC-001/002
- **Preconditions:** `SETTINGS_MANAGE`.
- **Trigger:** Format change/new branch.
- **Main flow:** 1) Choose document type + branch → 2) set prefix/suffix/width and next-number guard → 3) save → 4) new allocations follow format; history never renumbered.
- **E1:** Attempt to set next number below highest used → rejected.
- **Postconditions:** Series configured; audited.

## UC-SET-002 — Configure Company & Fiscal Year
**Actor:** Owner · **Pri:** M · **FRs:** FR-SET-001…004,015
- **Preconditions:** `SETTINGS_MANAGE`.
- **Trigger:** Initial setup/annual review.
- **Main flow:** 1) Company profile/legal/tax → 2) fiscal year (July–June), timezone/number formats → 3) currency/rounding, VAT mode → 4) save; calendar/periods generated.
- **Postconditions:** System-wide settings applied; audited.

## UC-SET-003 — Configure Approval Thresholds
**Actor:** Owner · **Pri:** M · **FRs:** FR-SET-006, FR-RBAC-011
- **Preconditions:** `SETTINGS_MANAGE`.
- **Trigger:** Policy change.
- **Main flow:** 1) Set thresholds: discount, credit override, expense, adjustment/write-off, transfer, backdate, period override → 2) map to roles → 3) save; enforcement and dual control apply at next action.
- **Postconditions:** Thresholds enforced server-side; audited.

## UC-SET-004 — Configure Templates & Notification Channels
**Actor:** Owner/Adm · **Pri:** S · **FRs:** FR-SET-012,013, FR-NOTIF-009,010,011
- **Preconditions:** `SETTINGS_MANAGE`.
- **Trigger:** Branding/provider change.
- **Main flow:** 1) Edit document templates (logo, fields, copies, footer) with preview → 2) configure email/SMS providers + sender identity (credentials encrypted) → 3) manage message templates with variable preview → 4) save; changes apply to new docs/messages.
- **E1:** Provider test fails → save allowed with warning; delivery failures alerted.
- **Postconditions:** Templates/providers active; credentials never exposed via API.

## UC-MIG-001 — Import Opening Data
**Actor:** Acct/SA · **Pri:** M (go-live) · **FRs:** FR-FIN-022, A-036, Phase 11
- **Preconditions:** Templates completed; opening date configured; staging dry-run done.
- **Trigger:** Go-live import window.
- **Main flow:** 1) Import masters (medicines, customers, suppliers) → 2) import opening stock as batches + `OPENING` stock movements → 3) import opening receivables/payables as `OPENING` ledger entries → 4) import account opening balances → 5) create users → 6) validation + reconciliation reports → 7) freeze cutover.
- **E1:** Validation failures → row-level report; nothing partially imported (per-file transaction).
- **E2:** Duplicate batch keys → merge per documented policy.
- **Postconditions:** Opening balances auditable; no fake documents used.

---

*End of use-case catalog. Continue to `docs/02-analysis/workflows.md`.*
