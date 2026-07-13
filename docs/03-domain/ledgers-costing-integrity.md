# Ledgers, Costing & Database Integrity

**Document ID:** DOC-LED-001
**Parent:** `docs/03-domain-model.md`
**Status:** Normative — this document is the design authority for money, stock, and concurrency behavior.

---

## 1. Ledger Framework (applies to all four ledgers)

| Property | Design |
|---|---|
| Shape | Append-only rows; no UPDATE/DELETE paths in the ORM/service layer; DB user for the app is granted INSERT/SELECT only on ledger tables (UPDATE allowed only for `cached balance` tables) |
| Identity | `id` UUIDv7 + `seq BIGINT GENERATED ALWAYS AS IDENTITY` for strict ordering and pagination |
| Source traceability | Every entry carries `source_type` + `source_id` + `source_number` (document) and `transaction_group_id` (groups entries posted by one operation, e.g., account transfer pair, sale confirm) |
| Actor | `created_by`, `created_at` (UTC), `business_date` (local), `branch_id` |
| Signs | Ledgers use **signed deltas** (`amount_delta`, `qty_delta`) plus explicit `entry_type`; a debit/credit boolean is avoided to prevent sign-convention drift. Balance conventions: receivable + / payable − / account + (asset). |
| Balances | Derived with `SUM(delta)` over filtered rows; caches maintained transactionally; nightly reconciliation rebuilds and compares (`ledgers-costing` §7) |
| Opening balances | `entry_type = OPENING`, posted via the migration tool (Phase 11); never via fake documents |
| Corrections | Compensating entries; the original + reversal share `reverses_entry_id` links |
| Idempotency | Each ledger row carries `idempotency_key` (unique per ledger where applicable) so replays cannot double-post |
| Immutability enforcement | DB trigger rejects UPDATE/DELETE on ledger tables as a second line of defense (app-level already prevents) |

**Cached balance update pattern (single choke-point service):**

```sql
-- inside the same transaction as the ledger INSERT
UPDATE stock_balance
   SET qty_on_hand = qty_on_hand + :qty_delta,
       version     = version + 1,
       updated_at  = now()
 WHERE branch_id = :branch AND medicine_id = :med AND batch_id = :batch;
-- row must already be locked (SELECT ... FOR UPDATE) in this transaction
```

If the cache update affects 0 rows, the transaction aborts (`BALANCE_ROW_MISSING`) — the invariant is that a balance row always exists for any batch with movements.

---

## 2. Inventory Ledger — `InventoryTransaction` (DB-INV-002)

| Field | Type | Notes |
|---|---|---|
| `entry_type` | enum | PURCHASE_IN, SALE_OUT, SALES_RETURN_IN, PURCHASE_RETURN_OUT, ADJUSTMENT_IN/OUT, EXPIRY_WRITE_OFF, DAMAGE_WRITE_OFF, PROMO_ISSUE, PROMO_REPLENISH, QUARANTINE_MOVE, OPENING, CANCELLATION_REVERSAL |
| `qty_delta` | NUMERIC(14,3) | Base units; positive in, negative out; never zero |
| `unit_cost` | NUMERIC(14,4) | Batch actual cost at movement time (for outbound, the batch cost; for inbound, newly computed effective cost) |
| `value_delta` | NUMERIC(14,2) | `qty_delta × unit_cost` rounded; stored for fast valuation/queries |
| `pool` | enum | Which balance bucket moves: SALEABLE / PROMO / QUARANTINE (BR-INV-011, DB-INV-002) |
| `source_type/source_id/source_number` | text/uuid/text | Purchase, SalesInvoice, SalesReturn, PurchaseReturn, StockAdjustment, Opening |
| `transaction_group_id` | uuid | Groups multi-line operation postings |
| `idempotency_key` | text unique | Prevents double posting on retries |

**Derived quantities:** `stock_balance.qty_on_hand`, `qty_promo`, `qty_quarantine` per (branch, medicine, batch) are sums filtered by `entry_type`/`pool`. Saleable quantity = `qty_on_hand − qty_quarantine − qty_promo` (promo and quarantine pools are tracked separately and never included in saleable availability).

---

## 3. Customer Ledger — `CustomerLedgerEntry` (DB-SALE-002)

| Field | Type | Notes |
|---|---|---|
| `entry_type` | enum | OPENING, INVOICE, PAYMENT, PAYMENT_REVERSAL, SALES_RETURN, RETURN_REVERSAL, ADVANCE_APPLIED, ADVANCE_REFUND, WRITE_OFF, ADJUSTMENT |
| `amount_delta` | NUMERIC(14,2) | Receivable convention: invoice +, payment −, return −, opening + |
| `source_type/source_id/source_number` | | Document link |
| `transaction_group_id`, `idempotency_key`, `reverses_entry_id` | | As per framework |
| `due_date` | date | On invoice entries only; drives aging |

**Derived values:** outstanding balance = Σ `amount_delta`. Invoice-level outstanding = invoice total − Σ allocations; advance balance = negative customer balance (or dedicated `advance_balance` cache on customer). Aging buckets are computed from invoice `due_date` and unpaid remainder.

---

## 4. Supplier Ledger — `SupplierLedgerEntry` (DB-PUR-002)

| Field | Type | Notes |
|---|---|---|
| `entry_type` | enum | OPENING, PURCHASE, PAYMENT, PAYMENT_REVERSAL, PURCHASE_RETURN, RETURN_REVERSAL, ADVANCE_APPLIED, ADJUSTMENT |
| `amount_delta` | NUMERIC(14,2) | Payable convention: purchase +, payment −, return −, opening + |
| `due_date`, `source_*`, `transaction_group_id`, `idempotency_key`, `reverses_entry_id` | | As per framework |

**Derived values:** payable balance = Σ `amount_delta`; purchase-level outstanding = purchase total − allocated payments − confirmed return value; aging from `due_date` (purchase date + credit days).

---

## 5. Financial Account Ledger — `FinancialTransaction` (DB-FIN-002)

| Field | Type | Notes |
|---|---|---|
| `account_id` | FK | The account whose balance moves |
| `entry_type` | enum | OPENING, SALE_RECEIPT, PURCHASE_PAYMENT, EXPENSE, INCOME, TRANSFER_IN, TRANSFER_OUT, DEPOSIT, WITHDRAWAL, REFUND, ADVANCE_REFUND, CHEQUE_CLEARED, CHEQUE_BOUNCE_REVERSAL |
| `amount_delta` | NUMERIC(14,2) | Positive increases the account balance |
| `transfer_group_id` | uuid nullable | Links the out/in pair of a transfer (BR-FIN-009) |
| `source_*`, `transaction_group_id`, `idempotency_key`, `reverses_entry_id` | | As per framework |
| `reference` | text | Bank/MFS/cheque reference |

**Derived values:** account balance = Σ `amount_delta`; cash/cheque status views join payment records; daily funds position = balances grouped by branch/type.

---

## 6. Costing Model (DEC-008, final)

### 6.1 Batch actual cost with bonus allocation
For a purchase line: `effective_unit_cost = line_net_amount ÷ (purchased_qty + bonus_qty)` where `line_net_amount = qty×unit_cost − line_discount + allocated landed cost` (VAT excluded from inventory cost; input VAT is tracked separately for reporting). The base-unit cost is stored on the batch and used for all outbound valuation.

**Worked example:** 100 boxes × 500 BDT, 10% discount, 10 boxes bonus:
`line_net = 45,000`; `total_qty = 110`; `effective cost = 409.0909 BDT/box` (rounded to 4 dp for storage; valuation rounds per BR-DATA-002 at document level).

### 6.2 Outbound costing
- Sale movements post at the batch's cost (per base unit).
- Purchase-return movements reverse at the batch's cost.
- Sales returns reverse COGS at **original batch cost** (BR-SRET-003), not current cost.
- Adjustments use batch cost; write-offs quantify loss at batch cost.
- Historical movements are **never recalculated** (BR-PUR-009). "Last purchase cost" on the medicine is informational only.

### 6.3 Valuation
`stock valuation = Σ (qty_on_hand × batch.unit_cost)` per branch/medicine/batch, excluding quarantine/promo pools or shown separately. Batch cost is immutable post-confirmation (BR-BATCH-003), which makes valuation deterministic.

### 6.4 Profit
`gross profit = Σ net revenue (lines − line/invoice discounts − returns) − Σ COGS (movement values of SALE_OUT + SALES_RETURN_IN reversals)`. Expenses/other income adjust net profit (BR-FIN-003). All aggregates run on NUMERIC sums server-side, never floats.

---

## 7. Reconciliation (NFR-REL-003)

Nightly job per branch:
1. Recompute `stock_balance` from `inventory_transaction` per (branch, medicine, batch, pool); compare with cache; report deltas.
2. Recompute `customer.balance_cache` and invoice outstanding from `customer_ledger_entry` + allocations.
3. Recompute `supplier.balance_cache` and purchase outstanding.
4. Recompute `financial_account.balance_cache` from `financial_transaction`.
5. Persist a `ReconciliationRun` report; mismatches trigger alert + repair task (re-derive cache with audit entry); recurring mismatch ⇒ incident (EC-040).

---

## 8. Database Integrity & Concurrency

### 8.1 Transaction boundaries
Every business operation is exactly one transaction. The critical operations: sale confirm, purchase confirm, payment/collection post, supplier payment post, return confirm (both), adjustment post, expense/income post, account transfer, cancellation/reversal, sequence allocation (inside caller's transaction).

### 8.2 Isolation & locking
- Isolation: **READ COMMITTED** (PostgreSQL default) + explicit row locks for money/stock paths. Serializable isolation is *not* used (retry storms at SMB concurrency).
- `SELECT ... FOR UPDATE` with **fixed lock ordering**:
  1. Stock rows: by `(branch_id, medicine_id, batch_id)` ascending.
  2. Customer rows: by `customer_id` (credit checks + allocations).
  3. Invoice/purchase rows: by document id.
  4. Sequence rows: by series id.
  Locking in a different order is a code-review defect.
- Statement timeouts: `statement_timeout = 15s`, `lock_timeout = 5s` for API transactions; deadlock ⇒ retry up to 3× with jitter, then surface `CONFLICT_RETRY_FAILED`.
- Advisory locks are not used except a single per-branch sequence allocator alternative if profiling requires.

### 8.3 Overselling prevention — exact sequence (sale confirm)
```
BEGIN
  idempotency claim (insert key or return stored result)         -- BR-AUD-004
  validate draft + period + credit (lock customer row FOR UPDATE if credit) -- BR-SALE-005
  lock batch rows in (medicine, batch) order FOR UPDATE          -- BR-INV-010
  re-read stock_balance for each locked batch
  if any requested qty > saleable qty  -> raise INSUFFICIENT_STOCK (rollback)
  allocate sequence number FOR UPDATE                            -- BR-DOC-001
  INSERT inventory_transaction (SALE_OUT per batch)
  UPDATE stock_balance (qty_on_hand -= qty)                      -- check constraint qty_on_hand >= 0
  INSERT customer_ledger_entry (INVOICE, +grand_total)
  INSERT payment + allocations + financial_transaction (if paid at entry)
  UPDATE sales_invoice states + number + confirm metadata
  COMMIT
```
The DB `CHECK (qty_on_hand >= 0)` constraint (and the derived-pool checks) is the final backstop; any code path that would violate it aborts the transaction (NFR-DI-002).

### 8.4 Constraint catalog (representative)

| Constraint | Type | Definition |
|---|---|---|
| `uq_batch_identity` | UNIQUE | `(branch_id, medicine_id, batch_number, expiry_date)` |
| `uq_stockbalance_key` | UNIQUE | `(branch_id, medicine_id, batch_id)` |
| `ck_balance_nonneg` | CHECK | `qty_on_hand >= 0 AND qty_promo >= 0 AND qty_quarantine >= 0` |
| `ck_qty_positive` | CHECK | `qty > 0` on all document items |
| `ck_amount_nonneg` | CHECK | `amount >= 0` on payments/expenses/income |
| `uq_document_number` | UNIQUE | `(branch_id, doc_type, fiscal_year, number)` |
| `uq_sequence_scope` | UNIQUE | `(branch_id, doc_type, fiscal_year)` on `document_sequence` |
| `uq_allocation_invoice` | UNIQUE | `(payment_id, invoice_id)` on `payment_allocation` |
| `ck_alloc_positive` | CHECK | `amount > 0` on allocations |
| `uq_idempotency_actor` | UNIQUE | `(actor_id, endpoint, idempotency_key)` |
| `uq_medicine_code` | UNIQUE (partial) | `(code) WHERE deleted_at IS NULL` |
| `fk_*` | FK | All FKs `ON DELETE RESTRICT`/`PROTECT`; cascades are forbidden on financial data |
| `ck_alloc_le_outstanding` | service + trigger | Allocation ≤ invoice outstanding (re-checked under lock) |

### 8.5 Soft delete & uniqueness
Partial unique indexes exclude soft-deleted rows (`WHERE deleted_at IS NULL`) for codes (medicine, customer, supplier, user mobile/email). Deleting a referenced master is blocked; deactivation is the operational path (BR-DATA-006 analog).

### 8.6 Partitioning readiness
`inventory_transaction`, `customer_ledger_entry`, `supplier_ledger_entry`, `financial_transaction`, and `audit_log` are candidates for monthly RANGE partitioning by `created_at` (NFR-SCALE-002); the schema uses no cross-partition FKs from ledgers to documents (document is referenced by value + indexed id), so partitioning can be introduced without redesign.

### 8.7 Migration & backfill safety
Migrations use expand/contract (add nullable → backfill → enforce) to allow zero-downtime deploys (NFR-REC-003); backfills run in batched Celery jobs with progress and idempotency.

---

## 9. Cross-References

| Concern | Document |
|---|---|
| Entities & fields | `docs/03-domain/entities-01…04` |
| Relationships | `docs/04-erd.md` |
| Business rules | `docs/01-requirements/08-business-rules.md` |
| Edge cases (concurrency) | `docs/02-analysis/edge-cases.md` |
| State dimensions | `docs/02-analysis/state-machines.md` |
