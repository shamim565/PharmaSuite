# State Transitions

**Document ID:** DOC-STM-001
**Parent:** `docs/02-system-analysis.md`
**Rule:** Every transition is enforced by the domain service, requires its permission, and is audited (BR-AUD-001). Transitions not listed as valid are invalid by default.

---

## 1. Sales Invoice

### 1.1 Conflict analysis — single status chain vs reality
The brief suggested one chain: `Draft → Confirmed → Partially Paid → Paid → Cancelled → Partially Returned → Fully Returned`. This is **not representable as one linear status**: an invoice can be *Partially Paid + Partially Returned* at the same time, and a *Paid* invoice can later become *Partially Returned*. Recommendation (adopted): model **four orthogonal dimensions** and derive a display status. This preserves every combination without an exponential enum.

### 1.2 Dimensions

| Dimension | Values | Set by |
|---|---|---|
| `lifecycle` | DRAFT → CONFIRMED → CANCELLED (terminal) | Confirm / Cancel |
| `payment_status` | UNPAID → PARTIALLY_PAID → PAID (can regress on payment reversal) | Allocations |
| `return_status` | NONE → PARTIALLY_RETURNED → FULLY_RETURNED | Sales returns |
| `fulfillment_status` | PENDING → DELIVERED (optional, S) | Delivery update |

### 1.3 Valid transitions

| From → To | Trigger | Guard conditions | Permission |
|---|---|---|---|
| DRAFT → CONFIRMED | Confirm sale | Valid lines; stock available after lock; credit checks pass or override; period open | `SALE_CONFIRM` |
| DRAFT → DRAFT | Edit/delete | Creator/branch; no number allocated | `SALE_CREATE` |
| CONFIRMED → CANCELLED | Cancel | No payments (UNPAID); no returns (NONE); period open/override | `SALE_CANCEL` |
| UNPAID → PARTIALLY_PAID | Payment allocation | Σ allocations < grand total | `PAYMENT_COLLECT` |
| PARTIALLY_PAID → PAID | Payment allocation | Σ allocations = grand total | `PAYMENT_COLLECT` |
| PAID → PARTIALLY_PAID | Payment reversal | Reversal reduces allocated sum | `PAYMENT_REVERSE` |
| PARTIALLY_PAID → UNPAID | Payment reversal | All allocations removed | `PAYMENT_REVERSE` |
| NONE → PARTIALLY_RETURNED | Sales return confirm | 0 < returned value < invoice value | `SRET_CONFIRM` |
| PARTIALLY_RETURNED → FULLY_RETURNED | Sales return confirm | Returned qty = sold qty per line | `SRET_CONFIRM` |
| PENDING → DELIVERED | Delivery update | Invoice CONFIRMED | `SALE_DELIVER` |

### 1.4 Invalid transitions (must be rejected)

| Attempt | Error | Reason |
|---|---|---|
| DRAFT → PAID | `INVALID_STATUS_TRANSITION` | Payments only allocate to CONFIRMED invoices |
| CONFIRMED → CANCELLED (paid or returned) | `INVOICE_HAS_PAYMENTS` / `INVOICE_HAS_RETURNS` | Use return/credit note |
| CONFIRMED → DRAFT | `INVALID_STATUS_TRANSITION` | No un-confirmation; cancel or adjust |
| CANCELLED → anything | `INVALID_STATUS_TRANSITION` | Terminal state |
| FULLY_RETURNED → CONFIRMED/PAID | `INVALID_STATUS_TRANSITION` | Terminal dimension value |
| PARTIALLY_RETURNED → NONE | `INVALID_STATUS_TRANSITION` | Returns are not deletable |

### 1.5 Derived display status (for UI)
`CANCELLED` → "Cancelled"; else `FULLY_RETURNED` → "Fully Returned"; else `PAID` + `PARTIALLY_RETURNED` → "Paid • Partially Returned"; else `PAID` → "Paid"; `PARTIALLY_PAID` + any return → "Partial • Returned"; `PARTIALLY_PAID` → "Partially Paid"; else "Confirmed". Filters expose the raw dimensions as facets.

---

## 2. Purchase

| Dimension | Values |
|---|---|
| `lifecycle` | DRAFT → CONFIRMED → CANCELLED (terminal) |
| `payment_status` | UNPAID → PARTIALLY_PAID → PAID (regresses on reversal) |
| `return_status` | NONE → PARTIALLY_RETURNED → FULLY_RETURNED |

**Valid:** DRAFT→CONFIRMED (valid lines, no duplicate invoice conflict or override, period open); CONFIRMED→CANCELLED only if no payments and no returns **and** stock not consumed by later movements; payment/return transitions as in §1 with supplier-side permissions.
**Invalid:** CONFIRMED→DRAFT; any transition out of CANCELLED; cancellation when stock has been resold (`PURCHASE_STOCK_CONSUMED` → use purchase return).

---

## 3. Customer Payment

`ACTIVE → REVERSED (terminal)` with optional cheque sub-state `PENDING → CLEARED | BOUNCED`.
- ACTIVE→REVERSED: permission per period rule; allocations removed; invoice statuses recomputed.
- PENDING→CLEARED: account debit confirmed; allocations stand.
- PENDING→BOUNCED: becomes REVERSED automatically; invoices re-open; cheque register updated.
- Invalid: REVERSED→ACTIVE; CLEARED→PENDING; editing amounts in any state.

## 4. Supplier Payment

Same as §3 (`ACTIVE → REVERSED`, cheque `PENDING → CLEARED | BOUNCED`), with supplier-side effects (payable restore, purchase status recompute).

## 5. Sales Return

`DRAFT → CONFIRMED → REVERSED (terminal)`
- DRAFT→CONFIRMED: quantities ≤ returnable; condition set; period open.
- CONFIRMED→REVERSED: compensating entry with permission; invoice return status recomputed; stock/quarantine reversed.
- Invalid: CONFIRMED→DRAFT; any transition after REVERSED; delete of confirmed return.

## 6. Purchase Return

`DRAFT → CONFIRMED → REVERSED (terminal)`; pickup sub-state `PENDING_PICKUP → COLLECTED`.
- Stock and payable effects occur at CONFIRMED (BR-PUR-010).
- Invalid: REVERSED→CONFIRMED; deleting a confirmed return.

## 7. Stock Adjustment

`DRAFT → PENDING_APPROVAL → POSTED → REVERSED (terminal)` plus `PENDING_APPROVAL → REJECTED (terminal)`.
- DRAFT→POSTED directly when below threshold (auto-posting).
- PENDING_APPROVAL→POSTED only by an approver ≠ requester (dual control).
- POSTED→REVERSED: compensating adjustment; period rules apply.
- Invalid: REJECTED→POSTED; POSTED→DRAFT; edit after POSTED; posting decrease below available stock.

## 8. Expense / Income

**Expense:** `PENDING (or POSTED if under threshold) → POSTED → REVERSED`; `PENDING → REJECTED`.
**Income:** `POSTED → REVERSED` (no approval gate by default).
- Invalid: edit after POSTED; REVERSED→POSTED; posting into locked period without Owner override.

## 9. Medicine Batch

| From → To | Trigger | Guard |
|---|---|---|
| ACTIVE → DEPLETED | last unit consumed | qty = 0 |
| ACTIVE → EXPIRED | time passes expiry | automatic (daily job); no sale thereafter |
| ACTIVE → QUARANTINE | damaged/return-quarantine | permission `BATCH_STATUS` |
| ACTIVE → DAMAGED | damage write-off | approved adjustment |
| ACTIVE → RECALLED | recall action | `BATCH_RECALL` |
| QUARANTINE → DAMAGED | disposal decision | approved adjustment |
| QUARANTINE → ACTIVE | inspection passes | permission + audit (only if not expired) |

**Invalid:** EXPIRED→ACTIVE; DEPLETED→ACTIVE (use new receipt/batch); RECALLED→ACTIVE; DAMAGED→ACTIVE; any status change without audit; editing cost/expiry after movements (BR-BATCH-003).

## 10. Doctor Visit

`PLANNED → COMPLETED | MISSED | CANCELLED`; ad-hoc visits are created directly as `COMPLETED`.
- COMPLETED editable by owning MR within 24 h (configurable), afterwards BM/Admin only; every edit audited (BR-CRM-002).
- Invalid: MISSED→COMPLETED (create a new visit); delete after completion; editing samples after the edit window without elevated permission.

## 11. Fiscal Period

`OPEN → LOCKED → OPEN (override only)`.
- OPEN→LOCKED: Owner `PERIOD_LOCK`; checklist warnings acknowledged.
- LOCKED→OPEN: Owner `PERIOD_OVERRIDE` + reason; audited; triggers a "reopened period" alert to the audit log.
- Invalid: postings while LOCKED without override (`PERIOD_LOCKED`); backdating before the configured floor.

## 12. User Account

`PENDING_ACTIVATION → ACTIVE ⇄ DEACTIVATED → SOFT_DELETED` (last Owner and self protected).
- PENDING→ACTIVE: activation/invite accepted.
- ACTIVE→DEACTIVATED: sessions revoked immediately (BR-AUTH-003).
- DEACTIVATED→ACTIVE: reactivation with role re-check.
- Invalid: deleting users with history (soft delete only); deactivating last active Owner.

## 13. Notification

`UNREAD → READ` (bulk mark-all applies). Immutable content; no other transitions.

---

## Transition → Event → Audit Matrix

| Entity | Event | Audit payload includes |
|---|---|---|
| SalesInvoice | confirm/cancel | dimensions before/after, number, actor, branch, overrides |
| Payment | post/reverse/cheque status | allocations before/after, account, reference |
| PurchaseReturn / SalesReturn | confirm/reverse | lines, quantities, condition, cost/VAT reversal |
| StockAdjustment | submit/approve/reject/post/reverse | reason, approver, qty delta |
| MedicineBatch | status change | old/new status, reason, actor |
| FiscalPeriod | lock/unlock | period, reason, checklist acknowledgments |
| User | activate/deactivate/role change | roles/branches before/after |
