# Business Rules

**Document ID:** DOC-BR-001
**Parent:** `docs/01-requirements-specification.md`
**Status:** Normative — backend must enforce all rules server-side (DEC-010). Any UI behavior that contradicts a rule is a defect.

> Rules are grouped by domain. "Enforcement" states where the rule is guaranteed (service layer, DB constraint, or both).

---

## 1. Data Integrity & Rounding (BR-DATA)

| ID | Rule | Enforcement |
|---|---|---|
| BR-DATA-001 | All monetary values use exact decimal types (`NUMERIC(14,2)` amounts, `NUMERIC(14,4)` unit prices/costs); quantities use `NUMERIC(14,3)`; floating point is forbidden in money/quantity paths | DB schema + code review |
| BR-DATA-002 | Each line is rounded half-up to 2 decimals; document totals are the sum of rounded lines; a round-off line adjusts the grand total to the nearest whole BDT, bounded at ±0.50 | Service layer + tests |
| BR-DATA-003 | VAT is computed on the discounted net line value at the medicine's rate | Service layer |
| BR-DATA-004 | Negative quantities, negative prices, and negative threshold amounts are rejected at API and DB level | Serializer + DB check |
| BR-DATA-005 | Timestamps are stored in UTC; business dates are local (Asia/Dhaka) dates; reports group by business date | Service layer |
| BR-DATA-006 | No business record is updated silently: every mutation goes through the service layer and emits an audit entry | Architecture + audit tests |

## 2. Authentication & Session Rules (BR-AUTH)

| ID | Rule | Enforcement |
|---|---|---|
| BR-AUTH-001 | Passwords are hashed with Argon2id; policy (length/complexity) is configurable and enforced at set/change time | Service layer |
| BR-AUTH-002 | Access tokens live ≤ 15 min; refresh tokens rotate on every use; a reused refresh token revokes its entire session family | Auth service |
| BR-AUTH-003 | Deactivation, password reset, or forced logout immediately revokes all sessions of that user | Auth service |
| BR-AUTH-004 | TOTP 2FA is mandatory for Owner/Admin roles when the company enables it; recovery codes are single-use | Auth service |

## 3. Roles & Permission Rules (BR-RBAC)

| ID | Rule | Enforcement |
|---|---|---|
| BR-RBAC-001 | Every API endpoint is permission-checked server-side; default is deny; UI hiding is never the control | Middleware + tests |
| BR-RBAC-002 | Effective permissions = union of granted roles minus explicit denies; deny wins | RBAC engine (unit-tested) |
| BR-RBAC-003 | No user may grant a permission they do not themselves hold (Owner exempt) | RBAC engine |
| BR-RBAC-004 | Cost/profit fields are masked at serializer level for users without `VIEW_COST`/`VIEW_PROFIT` | Serializers + API tests |

## 4. Branch Isolation Rules (BR-BRANCH)

| ID | Rule | Enforcement |
|---|---|---|
| BR-BRANCH-001 | Every operational document and ledger entry carries `branch_id`; stock, sequences, and accounts are branch-scoped | Schema + querysets |
| BR-BRANCH-002 | Access to an unassigned branch's data returns 403/404 without revealing existence | Query scoping + security tests |
| BR-BRANCH-003 | Consolidated multi-branch views require the `all_branches` scope; assigned-only roles can never aggregate across branches | RBAC + query layer |

## 5. Document, Numbering & Period Rules (BR-DOC)

| ID | Rule | Enforcement |
|---|---|---|
| BR-DOC-001 | Document numbers are gapless per branch and fiscal year, allocated inside the confirmation transaction (A-014) | Sequence table with row lock |
| BR-DOC-002 | Numbers are never reused or renumbered; cancelled documents keep their number and show VOID status | Service layer |
| BR-DOC-003 | Backdating is allowed only within an open fiscal month and requires `DOC_BACKDATE`; locked periods always return `PERIOD_LOCKED` | Service layer |
| BR-DOC-004 | Fiscal months lock after close; only Owner may reopen/posting-override with `PERIOD_OVERRIDE`, reason, and audit | Period service |
| BR-DOC-005 | Confirmed documents are immutable; corrections happen via cancel, return, credit/debit note, or compensating entry | Service layer (no update paths) |
| BR-DOC-006 | Draft documents have zero stock, ledger, or account effect | Service layer |

## 6. Audit & Idempotency Rules (BR-AUD, BR-IDEMP)

| ID | Rule | Enforcement |
|---|---|---|
| BR-AUD-001 | Every create/update/confirm/cancel/reverse/override on business data writes an immutable audit entry (actor, branch, entity, before/after, request-id, IP) | Audit middleware/service |
| BR-AUD-002 | Audit records cannot be updated or deleted through the application | DB permissions + no endpoints |
| BR-AUD-003 | Sensitive overrides — below-cost sale, credit override, FEFO override, duplicate supplier invoice, no-invoice return, free goods, backdate, period override, write-off above threshold — require a reason code and appear in the Exception Report (FR-RPT-024) | Service layer + report |
| BR-AUD-004 | Every POST that creates a financial or inventory document requires an `Idempotency-Key`; replaying the key returns the original result without side effects | Middleware + unique constraint |

## 7. Inventory Rules (BR-INV)

| ID | Rule | Enforcement |
|---|---|---|
| BR-INV-001 | Stock exists only as (branch, medicine, batch); there is no branch-pooled or company-level stock | Schema |
| BR-INV-002 | A batch quantity can never go below zero; outbound operations validate and the DB constraint backstops | Service layer + check constraint |
| BR-INV-003 | Stock is deducted only at document confirmation, never at draft creation | Service layer |
| BR-INV-004 | Outbound batch selection is FEFO (earliest expiry first, then earliest receipt); override requires `INV_OVERRIDE_FEFO` + reason | Allocation service |
| BR-INV-005 | Expired batches are never saleable; attempted sale fails with `BATCH_EXPIRED`; disposal only via write-off adjustment | Allocation service |
| BR-INV-006 | Batches within the near-expiry threshold (default 90 days, per-medicine override) are flagged; selling within 30 days of expiry or after expiry requires override permission | Alert job + allocation service |
| BR-INV-007 | The stock ledger is append-only; there are no update/delete paths | Schema + service layer |
| BR-INV-008 | Cached balances are updated in the same transaction as ledger entries and are rebuildable from the ledger; nightly reconciliation verifies and repairs with alerting | Transactions + reconciliation job |
| BR-INV-009 | Every stock movement references its source document (purchase, sale, return, adjustment, opening, promo issue) | Schema |
| BR-INV-010 | Concurrent outbound operations lock stock rows in deterministic key order (medicine, batch) with bounded retry; overselling is impossible by construction and by constraint | Transaction design + concurrency tests |
| BR-INV-011 | Promotional stock is a separate non-saleable pool; promo issues (doctor samples) never reduce saleable stock and vice versa | Service layer |

## 8. Batch & Expiry Rules (BR-BATCH)

| ID | Rule | Enforcement |
|---|---|---|
| BR-BATCH-001 | Batch identity = branch + medicine + batch number + expiry; receipts into an existing identity add quantity | Unique constraint |
| BR-BATCH-002 | Expiry is mandatory for all medicine items; only items flagged `no_batch` (consumables) are exempt | Serializer + schema |
| BR-BATCH-003 | Batch effective cost is immutable after confirmation; corrections only via authorized adjustment with audit | Service layer |
| BR-BATCH-004 | Allowed batch status transitions: active → depleted (qty 0), active → quarantine/damaged (write-off path), active → expired (time-based), active → recalled (recall action); keine transition out of expired/depleted/recalled except via authorized adjustment | State machine service |

## 9. Purchasing Rules (BR-PUR)

| ID | Rule | Enforcement |
|---|---|---|
| BR-PUR-001 | Purchase confirmation atomically creates/merges batches, posts stock movements, posts supplier payable, posts any immediate payment to accounts, and allocates the purchase number | Transaction |
| BR-PUR-002 | Bonus quantity increases batch quantity at zero invoice price; effective unit cost = line net amount ÷ (purchased qty + bonus qty); this cost drives COGS | Costing service |
| BR-PUR-003 | Duplicate (supplier + supplier invoice number) is blocked; `PUR_DUP_INVOICE` override with reason is audited and reported | Validation service |
| BR-PUR-004 | One purchase line = one batch identity; multiple batches require multiple lines | Schema/validation |
| BR-PUR-005 | Purchases are editable only in DRAFT; a confirmed purchase is immutable | Service layer |
| BR-PUR-006 | A confirmed purchase can be cancelled only when it has zero allocated payments and zero returns; cancellation posts reversing entries and retains the number | Reversal service |
| BR-PUR-007 | Purchase return quantity per line ≤ purchased quantity − already returned quantity | Return service + constraint |
| BR-PUR-008 | A purchase return reduces supplier payable; if payable would go below zero, the excess becomes supplier advance/receivable per supplier setting | Finance service |
| BR-PUR-009 | Confirmed purchase prices update the medicine's "last purchase cost" for reference only; historical COGS is never recalculated | Costing service |
| BR-PUR-010 | Confirmed purchase returns reduce batch stock immediately (goods leave); condition is recorded for traceability | Return service |

## 10. Sales Rules (BR-SALE)

| ID | Rule | Enforcement |
|---|---|---|
| BR-SALE-001 | Every confirmed invoice has a real customer; walk-in pseudo-customer only when the feature flag is enabled | Validation |
| BR-SALE-002 | Invoice numbers are allocated at confirmation, gapless per branch per fiscal year | Sequence service |
| BR-SALE-003 | Confirmation is atomic: number allocation, stock deduction (FEFO batches), stock ledger, customer receivable, paid-amount account transaction, and status all commit or none do | Transaction |
| BR-SALE-004 | Drafts do not reserve stock; availability is re-validated atomically at confirmation | Service layer |
| BR-SALE-005 | Credit sales respect credit limit and overdue rules; exceeding requires `SALE_OVERRIDE_CREDIT` + reason (audited, reported) | Credit control service |
| BR-SALE-006 | Selling below batch cost or below the configured margin floor requires `SALE_BELOW_COST` + reason (audited, reported) | Pricing service |
| BR-SALE-007 | Invoice totals = Σ rounded line nets + VAT + round-off; discounts at line and invoice level (invoice discount allocated pro-rata to lines for VAT/margin) | Totals service + tests |
| BR-SALE-008 | Cancellation is allowed only when the invoice has no payments and no returns; cancellation reverses stock and ledger effects, keeps the number as VOID, and is audited | Reversal service |
| BR-SALE-009 | Invoices with payments or returns are never cancelled; corrections use sales return/credit note (refund) instead | State machine |
| BR-SALE-010 | All corrections are compensating entries; original documents and ledger entries remain | Ledger design |
| BR-SALE-011 | Backdated invoicing only within open periods with `DOC_BACKDATE`; period lock always enforced | Period service |
| BR-SALE-012 | Prescription-required items follow company Rx policy (warn / require reference / off); control-class items additionally require `SALE_CONTROLLED` | Validation service |
| BR-SALE-013 | Doctor attribution on a line is optional metadata and never changes price, stock, or tax | Service layer |
| BR-SALE-014 | Free-goods lines (manual or scheme) are zero-price, require permission, deduct stock, and appear in the Exception Report | Validation + report |
| BR-SALE-015 | Sales bonus schemes (buy X get Y) generate an explicit zero-price bonus line; the scheme applied is stored on the invoice | Scheme service |

## 11. Payment & Collection Rules (BR-PAY)

| ID | Rule | Enforcement |
|---|---|---|
| BR-PAY-001 | Posted payments are immutable; mistakes are corrected by a reversal entry with permission and reason | Service layer |
| BR-PAY-002 | Default allocation is FIFO by invoice date with manual override; allocation never exceeds an invoice's outstanding amount; allocations lock invoice rows to prevent concurrent double-allocation | Allocation service + locks |
| BR-PAY-003 | Every payment method maps to exactly one financial account; account transactions are posted atomically with the payment | Finance service |
| BR-PAY-004 | Same-day reversals may be performed by Accountant; reversals affecting a locked/previous period require Owner with reason and are flagged in the reversal report | Reversal service |
| BR-PAY-005 | Receipt numbers are gapless per branch per fiscal year | Sequence service |
| BR-PAY-006 | Customer advances apply to new invoices only when auto-apply is enabled for that customer; otherwise they are applied manually | Collection service |
| BR-PAY-007 | Unallocated payment amounts are recorded as customer advance (on-account); they are never silently discarded | Collection service |
| BR-PAY-008 | A payment cannot exceed total outstanding for a single-invoice collection; excess must be an explicit advance (Q-026) | Validation |
| BR-PAY-009 | Cheque receipts remain Pending until cleared; bounced cheques trigger allocation reversal and invoice re-opening | Cheque service |

## 12. Sales Return Rules (BR-SRET)

| ID | Rule | Enforcement |
|---|---|---|
| BR-SRET-001 | Return lines reference the original invoice line and batch; returnable quantity = sold − already returned | Return service + constraint |
| BR-SRET-002 | Restock happens only for RESELLABLE, non-expired goods into the original batch; DAMAGED/EXPIRED goods go to the quarantine pool and are never saleable | Return service |
| BR-SRET-003 | COGS is reversed at the original batch cost; VAT and discounts are reversed proportionally | Finance service |
| BR-SRET-004 | Default refund is credit to the customer account; cash/bank refunds require `RETURN_REFUND` | Return service |
| BR-SRET-005 | Invoice status recomputes to PARTIALLY_RETURNED / FULLY_RETURNED after each return | State machine |
| BR-SRET-006 | Returns without an original invoice are allowed only with `SRET_NO_INVOICE` and are flagged in the Exception Report | Return service + report |
| BR-SRET-007 | A return's value cannot exceed the remaining invoice value (net of prior returns) | Validation |
| BR-SRET-008 | Returned bonus/free goods are returned to the batch as bonus quantities | Return service |

## 13. Finance & Profit Rules (BR-FIN)

| ID | Rule | Enforcement |
|---|---|---|
| BR-FIN-001 | Every money movement posts an append-only financial account transaction tied to an account and source document where applicable | Finance service |
| BR-FIN-002 | Customer/supplier/account balances are derived from ledgers; caches update transactionally and are verified nightly | Ledger design + job |
| BR-FIN-003 | Gross profit = net revenue (sales − returns − discounts) − COGS (batch actual cost at movement time); Net profit = gross profit − expenses + other income for the period | Reporting service |
| BR-FIN-004 | Discounts reduce revenue for profit and VAT base at line level | Totals service |
| BR-FIN-005 | Expenses and other income post immediately (subject to approval thresholds) and reverse only via compensating entries | Finance service |
| BR-FIN-006 | Opening balances are posted as `OPENING` entries with a configurable opening date; fake invoices/documents are never used | Import tooling |
| BR-FIN-007 | No posting into a locked period except Owner `PERIOD_OVERRIDE` with reason and audit | Period service |
| BR-FIN-008 | Account balances may go negative only when `allow_negative` is enabled on that account | Finance service + check |
| BR-FIN-009 | Account transfers are linked paired entries with one transfer reference; both post atomically | Finance service |

## 14. CRM Rules (BR-CRM)

| ID | Rule | Enforcement |
|---|---|---|
| BR-CRM-001 | Doctor master records are company-wide; MR assignments and visits are branch-scoped | Schema + scoping |
| BR-CRM-002 | A visit belongs to exactly one MR and one doctor; the MR may edit their own visit within 24 h (configurable), after which BM/Admin only; all edits audited | Visit service |
| BR-CRM-003 | Sales attribution keeps representative and doctor influence separate; reports never double-count value | Reporting service |
| BR-CRM-004 | Doctor samples are issued only from promotional stock and always link to doctor + visit | Promo service |
| BR-CRM-005 | Doctor–medicine mappings are effective-dated; reports for past periods use mappings as of the period end (not current mappings) | Mapping service |

---

## Rule Coverage Map

| Rule group | Primary FR modules | Primary tests (Phase 9) |
|---|---|---|
| BR-DATA | All | TC-DATA-* |
| BR-AUTH/BR-RBAC | FR-AUTH, FR-RBAC | TC-SEC-* |
| BR-BRANCH | FR-BRANCH | TC-BRANCH-* |
| BR-DOC | FR-SALE, FR-PUR, FR-ADJ | TC-DOC-* |
| BR-AUD/BR-IDEMP | FR-AUD, all write endpoints | TC-AUD-*, TC-CONC-* |
| BR-INV/BR-BATCH | FR-INV, FR-BATCH | TC-INV-*, TC-CONC-* |
| BR-PUR | FR-PUR, FR-PRET | TC-PUR-*, TC-PRET-* |
| BR-SALE | FR-SALE | TC-SALE-* |
| BR-PAY | FR-PAY, FR-PPAY | TC-PAY-* |
| BR-SRET | FR-SRET | TC-SRET-* |
| BR-FIN | FR-FIN, FR-EXP, FR-INC | TC-FIN-* |
| BR-CRM | FR-DOC, FR-DVIS, FR-REP | TC-DOC-*, TC-DVIS-* |
