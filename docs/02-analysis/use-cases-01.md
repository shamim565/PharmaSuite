# Use Cases — Part 1: Identity, Catalog, Inventory, Procurement

**Document ID:** DOC-UC-01
**Parent:** `docs/02-system-analysis.md`
**Format per UC:** Actor · Priority · Related FRs · Preconditions · Trigger · Main flow · Alternative flows (A#) · Exception flows (E#) · Postconditions · Notes

---

## UC-AUTH-001 — Sign In
**Actor:** All · **Pri:** M · **FRs:** FR-AUTH-001,002,004,009,010,016
- **Preconditions:** User account is active and not locked.
- **Trigger:** User submits credentials on the login screen.
- **Main flow:** 1) User enters mobile/email + password → 2) system verifies credentials → 3) (if 2FA enabled for role) challenges TOTP → 4) system issues access token + rotating refresh cookie → 5) system loads user's roles, permissions, branch set, default branch → 6) user lands on the role dashboard.
- **A1:** 2FA not enabled → skip step 3.
- **A2:** Multiple branches → branch switcher initialized to default branch (UC-BRANCH-002).
- **E1:** Invalid credentials → generic error (no user enumeration), failure logged, attempt counter incremented.
- **E2:** Account locked → `ACCOUNT_LOCKED` with unlock guidance.
- **E3:** Deactivated account → generic invalid-credential error.
- **Postconditions:** Session created; login event audited; permissions resolved.
- **Notes:** BR-AUTH-001/002. Rate limited per FR-AUTH-017.

## UC-AUTH-002 — Handle Account Lockout
**Actor:** System / Super Admin · **Pri:** M · **FRs:** FR-AUTH-003,017
- **Preconditions:** ≥ N failed attempts within the window.
- **Trigger:** Failed login threshold reached.
- **Main flow:** 1) System locks account for the configured duration → 2) notifications to user/admin (email/in-app) → 3) auto-unlock after window expires.
- **A1:** Admin unlocks early → audited.
- **E1:** Continued attempts during lockout → `ACCOUNT_LOCKED`, no counter reset.
- **Postconditions:** Lockout and unlock events audited.
- **Notes:** BR-AUTH-001.

## UC-AUTH-003 — Refresh Session Securely
**Actor:** System · **Pri:** M · **FRs:** FR-AUTH-009,010,014
- **Preconditions:** Valid refresh cookie present.
- **Trigger:** Access token near/at expiry or app resume.
- **Main flow:** 1) Client calls refresh → 2) server validates refresh token → 3) rotates token (old one invalidated) → 4) issues new access token → 5) continues session.
- **E1:** Refresh token reuse detected → entire session family revoked; user must re-authenticate; security event logged.
- **E2:** Refresh expired → forced login.
- **E3:** Idle beyond timeout → forced login with unsaved-form warning where feasible.
- **Postconditions:** New token pair; old refresh unusable.
- **Notes:** BR-AUTH-002.

## UC-AUTH-004 — Reset Forgotten Password
**Actor:** All · **Pri:** M · **FRs:** FR-AUTH-005,006,008
- **Preconditions:** Account active; self-service reset not disabled for the user.
- **Trigger:** "Forgot password" request.
- **Main flow:** 1) User submits identifier → 2) system sends single-use token (email/SMS) with generic confirmation → 3) user opens link, sets new password meeting policy and history → 4) all old sessions revoked → 5) user signs in.
- **E1:** Token expired/used → request again.
- **E2:** Policy/history violation → field errors.
- **Postconditions:** New password; reset audited; sessions revoked.
- **Notes:** BR-AUTH-001/003.

## UC-AUTH-005 — Logout All Devices
**Actor:** All / Super Admin (force) · **Pri:** M · **FRs:** FR-AUTH-011,012,013
- **Preconditions:** Authenticated.
- **Trigger:** User chooses "logout all devices" or admin forces logout.
- **Main flow:** 1) System revokes all refresh tokens for the user → 2) active access tokens expire naturally within ≤15 min → 3) confirmation shown.
- **E1:** Admin target is last Owner → blocked on deactivation paths, allowed for logout.
- **Postconditions:** All sessions invalid for refresh; event audited.

## UC-AUTH-006 — Manage TOTP 2FA
**Actor:** Adm+ · **Pri:** M · **FRs:** FR-AUTH-015
- **Preconditions:** Company 2FA policy allows/requires 2FA.
- **Trigger:** User enrolls in 2FA.
- **Main flow:** 1) System shows TOTP secret/QR → 2) user verifies a generated code → 3) system activates 2FA and issues one-time recovery codes → 4) future logins require TOTP.
- **E1:** Wrong verification code → retry; enrollment not activated.
- **E2:** Recovery code used → code invalidated; user prompted to re-enroll.
- **Postconditions:** 2FA active; audit recorded.

## UC-USER-001 — Create User with Roles/Branches
**Actor:** Adm+ · **Pri:** M · **FRs:** FR-USER-001,002,007,008
- **Preconditions:** Actor holds `USER_MANAGE`; roles and branches exist.
- **Trigger:** "New user" action.
- **Main flow:** 1) Enter name, unique mobile/email → 2) assign role(s) and branch set + default branch → 3) save → 4) invitation sent → 5) user activates and sets password → 6) user appears active.
- **A1:** Import users via CSV (FR-USER-011) with validation report.
- **E1:** Duplicate mobile/email → field error, nothing saved.
- **E2:** Role grant beyond actor's own permissions → blocked (BR-RBAC-003).
- **Postconditions:** User created (PENDING → ACTIVE), assignment audited.

## UC-USER-002 — Deactivate/Reactivate User
**Actor:** Adm+ · **Pri:** M · **FRs:** FR-USER-004,005,009
- **Preconditions:** Target user exists; actor authorized.
- **Trigger:** Deactivate/reactivate action.
- **Main flow:** 1) System checks target is not self and not last Owner → 2) status changes → 3) all sessions revoked (deactivate) → 4) history retained.
- **E1:** Self or last-Owner → blocked with explanation.
- **Postconditions:** Status change audited; historical documents keep attribution.

## UC-USER-003 — Admin-Reset User Password
**Actor:** Adm+ · **Pri:** M · **FRs:** FR-USER-003,014
- **Preconditions:** Target not marked "no self-service reset".
- **Trigger:** Admin issues reset.
- **Main flow:** 1) System generates reset link/temp credential → 2) all sessions revoked → 3) user must change password at next login → 4) reset audited.
- **E1:** Target locked for reset → refused.
- **Postconditions:** Password reset; forced change pending.

## UC-USER-004 — Review User Activity
**Actor:** Adm+ · **Pri:** S · **FRs:** FR-USER-013
- **Preconditions:** `AUDIT_VIEW` or user-management permission.
- **Trigger:** Open user activity view.
- **Main flow:** 1) Show last login, active sessions, recent audited actions → 2) drill-down to audit entries.
- **Postconditions:** Read-only; access itself audited (sensitive).

## UC-RBAC-001 — Manage Role Permissions
**Actor:** Super Admin · **Pri:** M · **FRs:** FR-RBAC-001,003,004,005,006,011,012
- **Preconditions:** Permission catalog available.
- **Trigger:** Edit/create/clone role.
- **Main flow:** 1) Choose/create role → 2) grant/deny permissions by module → 3) set branch scope → 4) preview effective permissions → 5) save → 6) change audited → 7) affected users see new permissions at next token refresh/request.
- **A1:** Clone existing role as template.
- **E1:** Attempt to grant permissions the actor lacks → blocked (Owner exempt).
- **E2:** Removing a permission that blocks in-flight work → warning lists affected users (informational).
- **Postconditions:** Role updated; runtime enforcement immediate at API layer.
- **Notes:** BR-RBAC-001/002/003.

## UC-RBAC-002 — Enforce Branch-Scoped Access
**Actor:** System · **Pri:** M · **FRs:** FR-RBAC-009, FR-BRANCH-012, BR-BRANCH-002
- **Preconditions:** Any scoped API request.
- **Trigger:** Request includes/serves branch-scoped data.
- **Main flow:** 1) Middleware resolves user's branch scope → 2) querysets filtered by permitted branches → 3) object access outside scope returns 404/403 without existence leak → 4) denied attempts logged.
- **E1:** `all_branches` scope → no filter (still permission-checked).
- **Postconditions:** Isolation enforced; violations audited.
- **Notes:** Security tests (TC-SEC-001) exercise IDOR on every document type.

## UC-BRANCH-001 — Manage Branches
**Actor:** SA/Owner · **Pri:** M · **FRs:** FR-BRANCH-001,002,007,011
- **Preconditions:** `BRANCH_MANAGE` permission.
- **Trigger:** Create/edit/deactivate branch.
- **Main flow:** 1) Enter code, name, contacts, legal/tax details, invoice prefixes → 2) save → 3) branch selectable by users/settings → 4) audited.
- **E1:** Duplicate code → rejected.
- **E2:** Deactivate with stock/balances/open dues → blocked with blocking list.
- **Postconditions:** Branch state changed; sequences/settings provisioned for new branch.

## UC-BRANCH-002 — Switch Branch Context
**Actor:** All multi-branch users · **Pri:** M · **FRs:** FR-BRANCH-004,005
- **Preconditions:** User assigned to ≥ 2 branches.
- **Trigger:** Branch switcher selection.
- **Main flow:** 1) User selects branch → 2) UI context indicator updates → 3) all lists/forms scope to that branch → 4) drafts in progress prompt confirmation.
- **E1:** User with one branch → switcher hidden.
- **Postconditions:** Context set; server re-scopes on every request (client context never trusted alone).

## UC-CAT-001 — Create/Edit Medicine
**Actor:** WM/Adm · **Pri:** M · **FRs:** FR-CAT-001…011,021,024,026
- **Preconditions:** Generic/manufacturer/category/units exist (or created inline).
- **Trigger:** "New medicine" action.
- **Main flow:** 1) Enter brand name, unique code, generic, manufacturer, category, dosage form/strength → 2) set base unit + pack conversions → 3) set prices per tier, VAT rate, shelf-life, expiry threshold, reorder level → 4) flags (Rx, controlled, cold-chain, no_batch) → 5) save → 6) medicine searchable.
- **E1:** Duplicate item code/barcode → rejected/warned.
- **E2:** Expiry mandatory flag missing for medicine item → validation error.
- **Postconditions:** Medicine active; price history starts; audited.

## UC-CAT-002 — Configure Expiry Thresholds & Margin Floor
**Actor:** Adm · **Pri:** M · **FRs:** FR-CAT-007,024, FR-SET-008,010
- **Preconditions:** `SETTINGS_MANAGE`.
- **Trigger:** Update threshold settings.
- **Main flow:** 1) Set company default near-expiry days and margin floor % → 2) optionally override per medicine → 3) save → 4) alerts/guards use new values from next evaluation (existing alerts recalculated on next job run).
- **Postconditions:** Settings applied; audited.

## UC-CAT-003 — Manage Generics/Manufacturers/Categories
**Actor:** Adm · **Pri:** M · **FRs:** FR-CAT-016,017,018
- **Preconditions:** `CATALOG_MANAGE`.
- **Trigger:** Create/edit/deactivate.
- **Main flow:** 1) Create record (hierarchy for categories) → 2) save → 3) available for medicine assignment.
- **E1:** Delete referenced by medicines → blocked (deactivate instead).
- **E2:** Category cycle → rejected.
- **Postconditions:** Master updated; audited.

## UC-CAT-004 — Import/Export Catalog
**Actor:** Adm · **Pri:** S · **FRs:** FR-CAT-014
- **Preconditions:** Template downloaded.
- **Trigger:** Upload CSV.
- **Main flow:** 1) Validate rows → 2) show error report → 3) import valid rows transactionally per file → 4) summary shown.
- **E1:** All rows invalid → nothing imported.
- **Postconditions:** Catalog updated; import audited.

## UC-CAT-005 — Merge Duplicate Medicine
**Actor:** Adm · **Pri:** S · **FRs:** FR-CAT-015
- **Preconditions:** Both records exist; duplicate identified.
- **Trigger:** Merge action.
- **Main flow:** 1) System checks neither/both have stock → 2) if safe, remaps conversions/mappings → 3) deactivates duplicate with alias → 4) audited.
- **E1:** Both have stock/transactions → blocked; resolve via adjustment/inventory correction first.
- **Postconditions:** Single active medicine; history preserved.

## UC-UNIT-001 — Manage Unit & Pack Conversions
**Actor:** WM · **Pri:** M · **FRs:** FR-UNIT-001…008
- **Preconditions:** Base unit exists.
- **Trigger:** Edit medicine units.
- **Main flow:** 1) Select base unit → 2) add conversions (box→strip→tablet) with exact factors → 3) validation (positive, acyclic, base=1, nested packs) → 4) save.
- **E1:** Invalid factor/cycle → rejected.
- **Postconditions:** Purchases/sales can use converted units; stock remains in base units.
- **Notes:** BR-DATA-001, BR-INV-022.

## UC-BATCH-001 — Batch Create/Merge on Receipt
**Actor:** System/WM (via purchase confirm) · **Pri:** M · **FRs:** FR-BATCH-001,002,004,006
- **Preconditions:** Purchase lines valid (medicine, batch no., expiry).
- **Trigger:** Purchase confirmation.
- **Main flow:** 1) For each line: compute effective unit cost (BR-PUR-002) → 2) find batch by (branch, medicine, batch no., expiry) → 3) create or add quantity → 4) record mfg/expiry/supplier/purchase ref → 5) post stock movement → 6) recompute cached balance.
- **E1:** Expiry in the past → blocked unless `RECEIVE_EXPIRED` override with reason.
- **E2:** Duplicate batch line within one purchase → merge into single line or warn.
- **Postconditions:** Batch available for FEFO; audited.

## UC-BATCH-002 — Mark Batch Recalled
**Actor:** WM/QA · **Pri:** S · **FRs:** FR-BATCH-012
- **Preconditions:** `BATCH_RECALL` permission.
- **Trigger:** Recall notice from manufacturer/supplier.
- **Main flow:** 1) Mark batch RECALLED → 2) sales blocked immediately → 3) impact report lists customers/invoices that received it → 4) disposal via write-off adjustment → 5) audited.
- **Postconditions:** Batch non-saleable; traceability report available.

## UC-BATCH-003 — Correct Batch Expiry Before Movement
**Actor:** WM/Adm · **Pri:** M · **FRs:** FR-BATCH-015
- **Preconditions:** Data-entry error identified; batch has no movements.
- **Trigger:** Edit expiry.
- **Main flow:** 1) Permission check → 2) edit expiry with reason → 3) before/after audited → 4) FEFO order recalculated.
- **E1:** Batch already has movements → blocked; use adjustment/corrective path.
- **Postconditions:** Corrected expiry; audit trail intact.

## UC-INV-001 — Post Stock Movement
**Actor:** System · **Pri:** M · **FRs:** FR-INV-001,002,003
- **Preconditions:** Source document confirmed.
- **Trigger:** Any document confirmation affecting stock.
- **Main flow:** 1) Validate document state → 2) append ledger entry(ies) with source ref, qty (base units), unit cost, actor → 3) lock and update cached balance transactionally → 4) commit.
- **E1:** Any failure → whole transaction rolls back (no partial postings).
- **Postconditions:** Immutable movement; balance consistent.
- **Notes:** BR-INV-007/008.

## UC-INV-002 — FEFO Batch Selection / Override
**Actor:** SO/BM · **Pri:** M · **FRs:** FR-INV-005,006, FR-BATCH-009,010
- **Preconditions:** Medicine has saleable batches in branch.
- **Trigger:** Adding a sale line.
- **Main flow:** 1) System lists active, non-expired batches ordered by expiry then receipt date → 2) allocates requested qty across batches → 3) shows allocation to user.
- **A1:** User overrides to a specific batch → requires `INV_OVERRIDE_FEFO` + reason; recorded.
- **E1:** No saleable stock → `INSUFFICIENT_STOCK` with alternatives (substitute suggestion FR-CAT-020).
- **E2:** Batch expired/near-expiry within block window → hidden or blocked per BR-INV-005/006.
- **Postconditions:** Allocation is only a proposal until confirmation, when it is re-validated.

## UC-INV-003 — Atomic Availability Validation
**Actor:** System · **Pri:** M · **FRs:** FR-INV-007,008,009, BR-INV-010
- **Preconditions:** Confirmation request with stock effect.
- **Trigger:** Confirm sale/purchase-return/adjustment decrease.
- **Main flow:** 1) Begin transaction → 2) lock involved batch rows in deterministic order (branch, medicine, batch id) → 3) re-read available quantities → 4) validate ≥ requested → 5) post movements and balances → 6) commit.
- **E1:** Insufficient after lock → rollback with `INSUFFICIENT_STOCK` details (batch, available, requested).
- **E2:** Lock contention/deadlock → bounded retry then same error path.
- **Postconditions:** Oversell impossible; concurrent confirms serialize correctly.
- **Notes:** Test TC-CONC-001 (two users, last stock).

## UC-INV-004 — Reconcile Cached vs Ledger Stock
**Actor:** System/Acct · **Pri:** M · **FRs:** FR-INV-020, NFR-REL-003
- **Preconditions:** Nightly job schedule.
- **Trigger:** Scheduled run (or manual run by admin).
- **Main flow:** 1) Compute ledger sums per (branch, medicine, batch) → 2) compare with cached balance → 3) mismatches: alert + repair task that re-derives the cache → 4) report retained.
- **E1:** Systematic mismatch (bug) → alert severity raised; investigation runbook.
- **Postconditions:** Cache verified/repaired; reconciliation report available.

## UC-INV-005 — View Stock & Expiry Reports
**Actor:** WM/BM · **Pri:** M · **FRs:** FR-INV-011…018, FR-RPT-010…016
- **Preconditions:** `STOCK_VIEW`; cost columns require `VIEW_COST`.
- **Trigger:** Open stock reports.
- **Main flow:** 1) Choose report (on-hand, valuation, expiry, low-stock, movement, slow/dead, batch detail) → 2) apply branch/date/category filters → 3) view/drill-down → 4) export (Excel/PDF/CSV).
- **E1:** Large export → async job + notification (UC-RPT-003).
- **Postconditions:** Read-only; export audited where it includes cost/profit.

## UC-ADJ-001 — Create Stock Adjustment
**Actor:** WM/BM · **Pri:** M · **FRs:** FR-ADJ-001,002,005,006
- **Preconditions:** Batch exists; reason codes configured.
- **Trigger:** Correction needed (count variance, damage, expiry, found stock).
- **Main flow:** 1) Select branch, medicine, batch → 2) direction and quantity + reason → 3) attach evidence (optional) → 4) system validates not below zero → 5) below threshold: post immediately; above: route to approval (UC-ADJ-002).
- **E1:** Decrease below available → rejected.
- **E2:** Locked period → `PERIOD_LOCKED` unless Owner override.
- **Postconditions:** Ledger entries posted (write-offs also post expense); audited.

## UC-ADJ-002 — Approve/Reject Adjustment
**Actor:** BM/Adm · **Pri:** M · **FRs:** FR-ADJ-003
- **Preconditions:** Adjustment in PENDING_APPROVAL above threshold.
- **Trigger:** Approver opens queue.
- **Main flow:** 1) Review detail + evidence → 2) approve → posts (as UC-ADJ-001 step 5) or reject with reason → 3) requester notified.
- **E1:** Approver = requester → blocked (dual control).
- **Postconditions:** POSTED or REJECTED; both audited.

## UC-ADJ-003 — Write Off Expired/Damaged Stock
**Actor:** WM/BM · **Pri:** M · **FRs:** FR-ADJ-004, FR-BATCH-010,011, BR-INV-005
- **Preconditions:** Expired/damaged/quarantine stock identified.
- **Trigger:** Disposal decision.
- **Main flow:** 1) Create adjustment type expiry-write-off/damage → 2) quantity ≤ batch qty → 3) approval per threshold → 4) ledger out + expense posting to configured category/account → 5) batch status/cached balance updated.
- **Postconditions:** Non-saleable stock removed from valuation; expense reflected in P&L; audited.

## UC-SUP-001 — Manage Supplier
**Actor:** WM/Acct · **Pri:** M · **FRs:** FR-SUP-001…014
- **Preconditions:** `SUPPLIER_MANAGE`.
- **Trigger:** Create/edit supplier.
- **Main flow:** 1) Enter identity (code unique), contacts, tax/legal data, payment terms, bank details → 2) save → 3) selectable on purchases/payments.
- **E1:** Duplicate code → rejected; duplicate warning (name/phone/BIN) → warn + confirm.
- **Postconditions:** Supplier active; audited.

## UC-SUP-002 — View Supplier Ledger/Statement
**Actor:** Acct · **Pri:** M · **FRs:** FR-SUP-005…008
- **Preconditions:** `SUPPLIER_VIEW`.
- **Trigger:** Open supplier ledger.
- **Main flow:** 1) Show append-only entries (opening, purchases, payments, returns, adjustments) → 2) date-range statement with opening/closing → 3) aging view with drill-down → 4) export/print.
- **E1:** Cost visibility restrictions → supplier ledger visible to accountants/owners only.
- **Postconditions:** Balances match reconciliation cache.

## UC-SUP-003 — Post Supplier Opening Balance
**Actor:** Acct · **Pri:** M · **FRs:** FR-SUP-004, FR-FIN-022
- **Preconditions:** Go-live/opening import window (Phase 11); `OPENING_POST` permission.
- **Trigger:** Opening balance entry/import.
- **Main flow:** 1) Enter supplier opening payable with as-of date → 2) system posts `OPENING` ledger entry → 3) aging includes it from the opening date.
- **E1:** Duplicate opening for same supplier → blocked/replaced only with Owner approval.
- **Postconditions:** Opening liability recorded cleanly (no fake invoices).

## UC-PUR-001 — Create Purchase Draft
**Actor:** WM · **Pri:** M · **FRs:** FR-PUR-001…007,015
- **Preconditions:** Supplier + medicines exist; `PURCHASE_MANAGE`.
- **Trigger:** "New purchase".
- **Main flow:** 1) Select supplier, branch, supplier invoice no./date → 2) add lines: medicine, batch no., mfg/expiry, qty (entry unit), bonus qty, unit cost, discount, VAT → 3) system computes totals, effective cost incl. bonus, margin preview (cost permission) → 4) attach invoice image → 5) save draft.
- **A1:** Landed cost (freight) entered and allocated (S).
- **E1:** Invalid expiry/dates → field errors.
- **E2:** Duplicate supplier invoice number → warning at entry; hard block at confirm (UC-PUR-003).
- **Postconditions:** Draft saved with zero stock/ledger effect.

## UC-PUR-002 — Confirm Purchase / Receive Stock
**Actor:** WM · **Pri:** M · **FRs:** FR-PUR-008…010, FR-BATCH-001, BR-PUR-001/002
- **Preconditions:** Draft valid; no duplicate invoice conflict; period open.
- **Trigger:** Confirm action.
- **Main flow:** 1) Re-validate all lines → 2) begin transaction → 3) allocate purchase number → 4) create/merge batches with effective cost → 5) post stock movements (purchase qty + bonus) → 6) post supplier payable → 7) post account transaction(s) for any payment at entry → 8) set status CONFIRMED (+payment status) → 9) commit → 10) show receipt/voucher, printable.
- **E1:** Duplicate supplier invoice (supplier+number) → blocked; override path (UC-PUR-003).
- **E2:** Failure mid-way → full rollback; draft remains editable; no number leak.
- **Postconditions:** Stock + payable + accounts updated atomically; audited.
- **Notes:** Idempotency-Key required (BR-AUD-004).

## UC-PUR-003 — Handle Duplicate Supplier Invoice
**Actor:** WM/Adm · **Pri:** M · **FRs:** FR-PUR-006, BR-PUR-003
- **Preconditions:** Confirm rejected due to duplicate (supplier, invoice number).
- **Trigger:** Review of block.
- **Main flow:** 1) System shows existing purchase for that invoice number → 2) user verifies (different invoice? corrected number?) → 3) if legitimate duplicate entry, cancel draft; if data-entry error, correct number; if genuine repeat invoice with `PUR_DUP_INVOICE`, override with reason → 4) confirm proceeds; override in Exception Report.
- **Postconditions:** No accidental double payables; exception recorded.

## UC-PUR-004 — Cancel Confirmed Purchase
**Actor:** Adm · **Pri:** M · **FRs:** FR-PUR-013, BR-PUR-006
- **Preconditions:** No payments allocated; no returns; period open.
- **Trigger:** Cancellation decision.
- **Main flow:** 1) System checks payment/return conditions → 2) reversal posts: reverse stock (if stock not yet sold — otherwise block), reverse payable, reverse account transaction → 3) status CANCELLED (number retained as VOID) → 4) audited.
- **E1:** Stock already consumed by sales → blocked; use purchase return (UC-PRET-001).
- **E2:** Payments allocated → blocked; reverse payments first.
- **Postconditions:** Reversed effects; audit intact.

## UC-PPAY-001 — Pay Supplier with Allocation
**Actor:** Acct · **Pri:** M · **FRs:** FR-PPAY-001…009, BR-PAY-002 (FIFO analog)
- **Preconditions:** Payable balance exists; `PAYMENT_POST`.
- **Trigger:** Payment decision.
- **Main flow:** 1) Select supplier, amount, method(s) + financial account(s), reference → 2) system proposes FIFO allocation to open purchases → 3) user may re-allocate manually → 4) validate Σ allocations ≤ amount, ≤ outstanding per purchase → 5) post payment + allocations + account transaction + update purchase statuses atomically → 6) voucher printable.
- **A1:** Advance (unallocated) → recorded as supplier advance per policy.
- **E1:** Allocation exceeds outstanding → blocked.
- **E2:** Account insufficient (no negative allowed) → `INSUFFICIENT_FUNDS`.
- **Postconditions:** Payables/account updated; audited; idempotency enforced.

## UC-PPAY-002 — Reverse Supplier Payment
**Actor:** Acct/Owner · **Pri:** M · **FRs:** FR-PPAY-004, BR-PAY-001/004
- **Preconditions:** Payment exists; permissions per period rules.
- **Trigger:** Error discovered.
- **Main flow:** 1) Enter reason → 2) system posts reversal (account + supplier ledger) → 3) allocations reversed; purchase statuses recomputed → 4) original + reversal linked → 5) audited.
- **E1:** Cross-period reversal → Owner only; flagged in reversal report.
- **E2:** Cheque already cleared → reversal allowed; if bounced, handled via rejection path.
- **Postconditions:** Payable restored; audit chain intact.

## UC-PPAY-003 — Supplier Cheque Lifecycle
**Actor:** Acct · **Pri:** S · **FRs:** FR-PPAY-007
- **Preconditions:** Payment method = cheque.
- **Trigger:** Cheque issued/presented.
- **Main flow:** 1) Record payment as Pending (no account debit until clearance per policy) → 2) mark Cleared → account debit posted → 3) or mark Bounced → payment reversed, purchase re-opened.
- **Postconditions:** Cheque register current; audited.

## UC-PRET-001 — Create/Confirm Purchase Return
**Actor:** WM · **Pri:** M · **FRs:** FR-PRET-001…010, BR-PUR-007/008/010
- **Preconditions:** Confirmed purchase with returnable quantity.
- **Trigger:** Return decision (damaged/expired/wrong item).
- **Main flow:** 1) Select purchase → 2) choose lines/batches and quantities ≤ returnable → 3) reason + destination → 4) totals + VAT reversal computed → 5) confirm atomically: batch stock decrease, supplier payable decrease (or advance), debit note number allocated → 6) print debit note.
- **E1:** Over-return → blocked with remaining quantity.
- **E2:** Locked period → `PERIOD_LOCKED`.
- **Postconditions:** Stock/payable updated; debit note issued; audited.

## UC-PRET-002 — Handle Pending Pickup
**Actor:** WM · **Pri:** S · **FRs:** FR-PRET-014
- **Preconditions:** Confirmed return goods awaiting supplier pickup.
- **Trigger:** Period review.
- **Main flow:** 1) List pending-pickup returns with age → 2) mark collected when dispatched → 3) aging report updates.
- **Postconditions:** Follow-up list current; audited.

---

*Continue to `docs/02-analysis/use-cases-02.md` for sales, CRM, finance and platform use cases.*
