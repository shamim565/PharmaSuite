# Edge Cases

**Document ID:** DOC-EC-001
**Parent:** `docs/02-system-analysis.md`
**Purpose:** Pre-analyzed corner cases with mandated handling. Each will become an automated test in Phase 9 (anticipated `TC-*` IDs shown).

| ID | Scenario | Mandated handling | Rules / FRs | Anticipated test |
|---|---|---|---|---|
| EC-001 | Same medicine exists in multiple batches and the customer buys one aggregated quantity | Persisted model is **one sale line per batch** (A-012). The entry screen may display an aggregated medicine row, but on save/confirm it splits into per-batch lines. FEFO determines the split | BR-INV-004, FR-SALE-003 | TC-INV-002 |
| EC-002 | Two users sell the last unit of the same batch simultaneously | Row lock on the batch (deterministic order) serializes confirms; first commits, second receives `INSUFFICIENT_STOCK` with live available qty | BR-INV-010, UC-INV-003 | TC-CONC-001 |
| EC-003 | Batch expires between draft creation and confirmation | Confirmation re-validates expiry; expired batch is rejected with `BATCH_EXPIRED`; user must switch batch (draft preserved) | BR-INV-005, FR-SALE-015 | TC-SALE-010 |
| EC-004 | Customer pays more than one invoice's outstanding | Collection blocks excess beyond outstanding; user may record the excess explicitly as customer advance | BR-PAY-008, Q-026 | TC-PAY-006 |
| EC-005 | Customer pays before any invoice exists | Amount recorded as customer advance (on-account); applied automatically at confirmation only if auto-apply enabled, else manually | BR-PAY-006/007 | TC-PAY-007 |
| EC-006 | Purchase is partially returned | Returnable quantity = purchased − returned; payable decreases; if payable would go negative, excess becomes supplier advance/receivable per supplier setting | BR-PUR-007/008 | TC-PRET-002 |
| EC-007 | Returned medicine arrives damaged | Condition = DAMAGED → quarantine pool; **no restock**; credit note still issued; quarantine write-off requires approval | BR-SRET-002, BR-INV-011 | TC-SRET-003 |
| EC-008 | Payment must be reversed after the period was locked | Only Owner may reverse with `PERIOD_OVERRIDE` + reason; reversal is flagged in the cross-period reversal report | BR-PAY-004, BR-FIN-007 | TC-PAY-008 |
| EC-009 | User tries to cancel an invoice that already has a payment | Cancellation blocked; system instructs to use sales return/credit note (refund) path | BR-SALE-009 | TC-SALE-005 |
| EC-010 | Discount makes the net price below batch cost | Blocked unless `SALE_BELOW_COST` + reason; recorded on the invoice and listed in the Exception Report | BR-SALE-006, BR-AUD-003 | TC-SALE-003 |
| EC-011 | Supplier invoice number already exists for that supplier | Confirmation blocked; override `PUR_DUP_INVOICE` with reason allowed; override appears in Exception Report | BR-PUR-003 | TC-PUR-003 |
| EC-012 | Stock adjustment was posted incorrectly | Compensating adjustment (reverse direction) with reason and permission; original retained; locked-period rules apply | BR-INV-007, FR-ADJ-007 | TC-ADJ-002 |
| EC-013 | Same medicine is stocked in multiple branches | Batches and balances are branch-scoped; no cross-branch pooling; consolidated reports aggregate only | BR-INV-001, BR-BRANCH-001 | TC-BRANCH-001 |
| EC-014 | User loses internet while sale confirmation is in flight | Client retries with the **same Idempotency-Key**; server returns the original invoice if committed, else processes once; UI reconciles state | BR-AUD-004, FR-SALE-017 | TC-CONC-002 |
| EC-015 | Two cashiers allocate payments to the same invoice concurrently | Invoice row lock during allocation; second request sees updated outstanding and cannot over-allocate | BR-PAY-002 | TC-CONC-003 |
| EC-016 | User enters a document dated inside a locked month | Rejected with `PERIOD_LOCKED`; only Owner override with reason proceeds and is audited | BR-DOC-003/004 | TC-FIN-002 |
| EC-017 | Supplier ships a batch whose batch number differs from the invoice | Treated as a new batch identity; invoice line corrected to physical batch number before confirmation | BR-BATCH-001 | TC-BATCH-002 |
| EC-018 | Purchase is recorded in boxes, sale happens in strips/tablets | All stock ledger quantities are base units; conversion factors are exact decimals; purchase cost allocated per base unit | BR-DATA-001, BR-INV-022 | TC-UNIT-001 |
| EC-019 | Two concurrent invoices would jointly exceed the customer's credit limit | Customer row locked during confirm; second confirmation evaluates updated exposure and blocks or requires override | BR-SALE-005 | TC-CONC-004 |
| EC-020 | Customer returns free/bonus goods | Returned quantities go back to the batch as bonus; customer ledger credit excludes the zero-price line; bonus stock restored | BR-SRET-008 | TC-SRET-004 |
| EC-021 | Zero-value/replacement invoice issued | Requires `SALE_ZERO_VALUE`; marked on invoice; appears in Exception Report | FR-SALE-029 | TC-SALE-007 |
| EC-022 | Selling a batch inside the near-expiry block window | Blocked unless `INV_SELL_NEAR_EXPIRY` override with reason; FEFO still prioritizes the earliest batch | BR-INV-006 | TC-INV-005 |
| EC-023 | Expiry typo discovered after batch has movements | Batch expiry is not editable post-movement; correct via adjustment/write-off and create/merge the correct batch going forward; incident documented | FR-BATCH-015, BR-BATCH-003 | TC-BATCH-003 |
| EC-024 | Double-tap on Confirm (duplicate submission) | Idempotency key returns the same document; no duplicate stock/ledger/payment effects | BR-AUD-004 | TC-CONC-002 |
| EC-025 | Payment and sales return race on the same invoice | Both operations lock the invoice row; deterministic ordering; final states recomputed from facts (allocations + returns) | BR-PAY-002, BR-SRET-005 | TC-CONC-005 |
| EC-026 | Account transfer form submitted twice | Idempotency key + unique transfer reference; second submission returns the original transfer | BR-AUD-004, FR-FIN-005 | TC-FIN-003 |
| EC-027 | Email/SMS provider outage during notification | Delivery fails soft; in-app notification remains authoritative; retries with backoff; admin alert after threshold | NFR-AVL-003, FR-NOTIF-012 | TC-NOTIF-002 |
| EC-028 | PWA offline cache shows stale stock; user confirms when back online | Server re-validates at confirmation and returns live shortage details if changed; UI prompts batch re-selection | DEC-005, FR-SALE-004 | TC-MOB-002 |
| EC-029 | Month-end lock attempted while approvals are pending or payments unallocated | Close checklist surfaces blocking/warning items; lock allowed only with explicit acknowledgment; pending approvals cannot post into the locked period | UC-FIN-007, BR-FIN-007 | TC-FIN-004 |
| EC-030 | Sales representative leaves the company with active assignments | Deactivation guard requires reassignment of customers/doctors; until reassigned, records remain visible historically | FR-REP-015 | TC-REP-002 |
| EC-031 | Two MRs log visits to the same doctor on the same day | Allowed — each visit belongs to its MR; coverage metrics count per assignment; no merge | BR-CRM-002 | TC-DVIS-002 |
| EC-032 | Insufficient promotional stock for planned samples | Sample issue blocked with available promo qty; options: replenish promo pool via purchase allocation or authorized promo adjustment (never saleable stock) | BR-INV-011, BR-CRM-004 | TC-DVIS-003 |
| EC-033 | Opening-stock import contains duplicate batch keys | Validator reports before commit; merge policy: same (branch, medicine, batch, expiry) rows combine quantities, costs must match or import is rejected for review | UC-MIG-001, A-036 | TC-MIG-001 |
| EC-034 | Wrong branch selected while entering a sale | Branch context is always visible and printed on documents; confirm screen shows branch; correction = cancel (if allowed) or return + re-invoice in correct branch | FR-BRANCH-005, BR-BRANCH-001 | TC-BRANCH-002 |
| EC-035 | Partial payment must be spread across several invoices | FIFO proposal by invoice date; manual re-allocation allowed for permitted roles; audited before/after | BR-PAY-002 | TC-PAY-009 |
| EC-036 | Customer cheque bounces after the period is locked | Reversal requires Owner; flagged in reversal report; invoices re-open; cheque register shows BOUNCED with history | BR-PAY-004/009 | TC-PAY-010 |
| EC-037 | Manager changes medicine price while an operator has a draft open | Prices are captured at line entry; draft shows "stale price" indicator with explicit re-price action; confirm uses captured prices and audit records them | FR-SALE-005, BR-AUD-001 | TC-SALE-011 |
| EC-038 | Return attempted on a fully returned invoice | Blocked with "fully returned" state; returns list remaining quantity = 0 | BR-SRET-001 | TC-SRET-005 |
| EC-039 | Adjustment approval is rejected | No stock/expense effect; requester notified with reason; adjustment remains REJECTED and audited | FR-ADJ-003 | TC-ADJ-003 |
| EC-040 | Nightly reconciliation finds a cache/ledger mismatch | Alert generated with deltas; repair task re-derives cache with audit entry; recurring mismatch escalates as incident | BR-INV-008, BR-FIN-002 | TC-INV-004 |
| EC-041 | Sale happens at 11:50 pm local time; report run after midnight | Business date = local date (Asia/Dhaka); timestamps stored UTC; reports group by business date so the sale belongs to the correct day | BR-DATA-005 | TC-DATA-002 |
| EC-042 | Item flagged no_batch (consumable) is purchased/sold | System auto-creates a per-branch pseudo-batch `DEFAULT` so ledger/balance design stays uniform; expiry/FEFO exempt; still no negative stock | FR-CAT-026, BR-BATCH-002 | TC-CAT-003 |
| EC-043 | Supplier short-ships (received qty < invoiced qty) | Confirm only received quantities; record supplier credit via purchase return/debit note for the shortfall (or supplier-issued credit noted in return); payable reflects actual received value | BR-PUR-001, BR-PUR-007 | TC-PUR-004 |
| EC-044 | Multiple payments collected from the same customer on the same day | Allowed; distinct sequential receipt numbers; auto-allocation processes in FIFO by invoice date, allocations validated under locks | BR-PAY-002/005 | TC-PAY-011 |
| EC-045 | User's branch assignment changes while they have an open draft | Every API request re-evaluates scope; confirm from a no-longer-permitted branch is rejected; draft retained and visible to permitted users of that branch | BR-BRANCH-002, FR-RBAC-009 | TC-SEC-002 |

---

## Categories Covered
- **Concurrency:** EC-002, 014, 015, 019, 024, 025, 026
- **State integrity:** EC-003, 009, 012, 016, 023, 029, 038, 039
- **Money/ledger correctness:** EC-004, 005, 006, 008, 010, 020, 035, 036, 040
- **Data quality:** EC-011, 017, 018, 033, 041, 042, 043
- **Operations/UX:** EC-021, 022, 027, 028, 030, 031, 032, 034, 037, 044, 045
- **Isolation/security:** EC-001, 013, 045
