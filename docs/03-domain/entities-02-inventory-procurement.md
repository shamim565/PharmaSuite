# Entity Catalog 2 — Inventory & Procurement

**Document ID:** DOC-ENT-02
**Parent:** `docs/03-domain-model.md`
**Conventions:** see `entities-01`. Ledger tables are append-only and immutable (framework in `ledgers-costing-integrity.md` §1).

---

## Inventory

### DB-INV-001 MedicineBatch
**Purpose:** The unit of stock ownership, expiry, and cost. Every saleable quantity belongs to exactly one batch.
| Field | Type | Req | Rules |
|---|---|---|---|
| `branch_id`, `medicine_id` | fk | ✔ | Identity part |
| `batch_number` | txt(60) | ✔ | Physical batch no.; `DEFAULT` pseudo-batch for `no_batch` items (EC-042) |
| `manufacturing_date` | date | ○ | ≤ expiry |
| `expiry_date` | date | ✔ except `no_batch` | Expiry mandatory (BR-BATCH-002) |
| `supplier_id` | fk→Supplier | ○ | First/latest supplier |
| `first_purchase_item_id` | fk→PurchaseItem | ○ | Traceability |
| `qty_received_total` | num(14,3) | ✔ | Sum of receipts incl. bonus |
| `unit_cost` | num(14,4) | ✔ | Effective cost per base unit; immutable after confirm (BR-BATCH-003) |
| `status` | enum | ✔ | ACTIVE / DEPLETED / EXPIRED / QUARANTINE / DAMAGED / RECALLED (state machine §9) |
| `recalled_at`, `recall_reason` | ts/txt | ○ | |
| `mfg_label`, `notes` | txt | ○ | |
**Relationships:** N:1 Medicine/Branch/Supplier; 1:N InventoryTransaction, StockAdjustmentItem; M:N via PurchaseItem/SalesInvoiceItem.
**Constraints/indexes:** unique `(branch_id, medicine_id, batch_number, expiry_date)`; idx `(branch_id, medicine_id, status, expiry_date)` for FEFO; idx `(expiry_date)` for alerts.
**Soft delete & audit:** never deleted; status changes audited; cost/expiry edits blocked post-movement (FR-BATCH-015).

### DB-INV-002 InventoryTransaction *(append-only ledger)*
| Field | Type | Req | Rules |
|---|---|---|---|
| `branch_id`, `medicine_id`, `batch_id` | fk | ✔ | Lock-scope key |
| `entry_type` | enum | ✔ | PURCHASE_IN, SALE_OUT, SALES_RETURN_IN, PURCHASE_RETURN_OUT, ADJUSTMENT_IN/OUT, EXPIRY_WRITE_OFF, DAMAGE_WRITE_OFF, PROMO_ISSUE, PROMO_REPLENISH, QUARANTINE_IN/OUT, OPENING, CANCELLATION_REVERSAL |
| `pool` | enum | ✔ | SALEABLE / PROMO / QUARANTINE — which balance bucket moves |
| `qty_delta` | num(14,3) | ✔ | Base units, signed, ≠ 0 |
| `unit_cost` | num(14,4) | ✔ | Batch cost at movement time |
| `value_delta` | num(14,2) | ✔ | `qty_delta × unit_cost` rounded |
| `source_type`, `source_id`, `source_number` | txt/uuid/txt | ✔ | Document traceability |
| `transaction_group_id` | uuid | ✔ | Groups one operation's entries |
| `reverses_entry_id` | fk→self | ○ | Compensating link |
| `idempotency_key` | txt | ✔ | Unique per entry |
| `business_date`, `created_by`, `created_at`, `seq` | | ✔ | Local date + UTC ts + identity sequence |
**Indexes:** `(branch_id, medicine_id, batch_id, seq)`, `(source_type, source_id)`, `(transaction_group_id)`, `(created_at)` (partition-ready).
**Immutability:** no UPDATE/DELETE; DB trigger enforces.

### DB-INV-003 StockBalance *(derived cache)*
| Field | Type | Req | Rules |
|---|---|---|---|
| `branch_id`, `medicine_id`, `batch_id` | fk | ✔ | Unique triple |
| `qty_on_hand` | num(14,3) | ✔ | Saleable pool; CHECK ≥ 0 |
| `qty_promo` | num(14,3) | ✔ | Promo pool; CHECK ≥ 0 |
| `qty_quarantine` | num(14,3) | ✔ | Quarantine pool; CHECK ≥ 0 |
| `version` | int | ✔ | Optimistic marker |
**Maintained by:** the single inventory posting service inside the same transaction as ledger inserts; rebuildable from ledger; reconciled nightly (§7 of ledger doc).
**Indexes:** unique key + `(branch_id, medicine_id)` partial where qty_on_hand > 0 for availability lists.

### DB-INV-004 StockAdjustment
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ○ | `ADJ-…`, allocated at post |
| `branch_id`, `business_date` | | ✔ | Period lock applies |
| `adjustment_type` | enum | ✔ | INCREASE / DECREASE |
| `reason_code` | enum | ✔ | DATA_CORRECTION, COUNT_VARIANCE, DAMAGE, EXPIRY_WRITE_OFF, FOUND_STOCK, PROMO_REPLENISH, RECALL_DISPOSAL |
| `status` | enum | ✔ | DRAFT / PENDING_APPROVAL / POSTED / REJECTED / REVERSED |
| `requested_by`, `approved_by`, `approved_at`, `posted_at` | | | Approver ≠ requester (dual control) |
| `reversal_of_id` | fk→self | ○ | Compensating link |
| `attachment_id` | fk→Attachment | ○ | Evidence |
| `note` | txt | ○ | |
**Rules:** decrease ≤ available; write-off types post expense; locked-period → `PERIOD_LOCKED` (BR-FIN-007).
**Audit:** every transition logged with reason.

### DB-INV-005 StockAdjustmentItem
`adjustment_id`, `medicine_id`, `batch_id`, `qty_delta` (± num), `unit_cost`, `pool` enum(SALEABLE/PROMO/QUARANTINE), `note`; check `qty_delta ≠ 0`, qty ≤ available.

### DB-INV-006 DocumentSequence
| Field | Type | Req | Rules |
|---|---|---|---|
| `branch_id`, `doc_type`, `fiscal_year` | | ✔ | Unique triple |
| `prefix`, `width` | txt/int | ✔ | Configured (FR-SET-005) |
| `next_number` | int | ✔ | Row-locked at allocation; never decreased |
**doc_type:** SALES_INVOICE, RECEIPT, CREDIT_NOTE, SUPPLIER_PAYMENT, DEBIT_NOTE, PURCHASE, ADJUSTMENT, RETURN_RECEIPT.
**Rules:** gapless allocation inside caller transaction; numbers never reused (BR-DOC-001/002).

---

## Procurement

### DB-PUR-001 Supplier
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(20) | ✔ | Unique among non-deleted |
| `name` | txt(200) | ✔ | Indexed |
| `supplier_type` | enum | ✔ | MANUFACTURER / IMPORTER / TRADER / DISTRIBUTOR |
| `contact_person`, `phone`, `email`, `address` | txt | ○ | |
| `bin`, `vat_reg`, `trade_license` | txt | ○ | |
| `credit_days` | int | ✔ | Default 0 (cash) |
| `preferred_payment_method` | enum | ○ | |
| `bank_details` | jsonb | ○ | Masked without payment permission |
| `excess_return_handling` | enum | ✔ | ADVANCE (default) / BLOCK |
| `balance_cache` | num(14,2) | ✔ | Payable, derived + reconciled |
| `status` | enum | ✔ | ACTIVE / INACTIVE |
**Soft delete:** deactivate when history exists; duplicate merge blocked if both have transactions.

### DB-PUR-002 SupplierLedgerEntry *(append-only)*
Per ledger framework: `entry_type` (OPENING, PURCHASE, PAYMENT, PAYMENT_REVERSAL, PURCHASE_RETURN, RETURN_REVERSAL, ADVANCE_APPLIED, ADJUSTMENT), `amount_delta`, `due_date`, `source_*`, `transaction_group_id`, `reverses_entry_id`, `idempotency_key`, `business_date`, `seq`.
**Indexes:** `(supplier_id, seq)`, `(supplier_id, due_date)`.

### DB-PUR-003 Purchase
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ○ | `PUR-…` at confirm; unique `(branch, fy, number)` |
| `supplier_id`, `branch_id`, `business_date` | | ✔ | |
| `supplier_invoice_number`, `supplier_invoice_date` | txt/date | ✔/✔ | Duplicate (supplier, number) blocked (BR-PUR-003) |
| `lifecycle` | enum | ✔ | DRAFT / CONFIRMED / CANCELLED |
| `payment_status` | enum | ✔ | UNPAID / PARTIALLY_PAID / PAID |
| `return_status` | enum | ✔ | NONE / PARTIALLY_RETURNED / FULLY_RETURNED |
| `subtotal`, `discount_total`, `vat_total`, `freight_total`, `round_off`, `grand_total` | num(14,2) | ✔ | Server-computed |
| `paid_total`, `returned_total` | num(14,2) | ✔ | Caches from allocations/returns |
| `attachment_id` | fk | ○ | Supplier invoice image/PDF |
| `confirmed_at/by`, `cancel_reason`, `reversal_group_id` | | ○ | |
| `idempotency_key` | txt | ○ | Unique for confirm |
**Rules:** editable only while DRAFT; cancel only when unpaid/unreturned and stock untouched (UC-PUR-004).
**Indexes:** `(branch_id, business_date)`, `(supplier_id, business_date)`, `(supplier_id, supplier_invoice_number)`, `(lifecycle)`.

### DB-PUR-004 PurchaseItem
`purchase_id`, `line_no`, `medicine_id`, `batch_number`, `manufacturing_date`, `expiry_date`, `entry_unit_id`, `qty_entered`, `conversion_factor`, `qty_base`, `bonus_qty_entered`, `bonus_qty_base`, `unit_cost` (per entry unit), `line_discount`, `vat_rate`, `vat_amount`, `line_net`, `effective_unit_cost` (per base unit, incl. bonus), `batch_id` (set at confirm), `landed_cost_share`.
**Rules:** one line = one batch (BR-PUR-004); totals recomputed server-side.

### DB-PUR-005 SupplierPayment
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ✔ | `PPV-…` gapless |
| `supplier_id`, `branch_id`, `business_date` | | ✔ | |
| `amount` | num(14,2) | ✔ | > 0 |
| `method` | enum | ✔ | CASH / BANK / MFS / CHEQUE |
| `account_id` | fk→FinancialAccount | ✔ | Method maps to account (BR-PAY-003) |
| `reference`, `cheque_no`, `cheque_date`, `cheque_status` | txt/date/enum | ○ | PENDING/CLEARED/BOUNCED |
| `status` | enum | ✔ | ACTIVE / REVERSED |
| `reversal_of_id`, `reversal_reason` | fk/txt | ○ | |
| `idempotency_key` | txt | ✔ | Unique |
**Indexes:** `(supplier_id, business_date)`, `(account_id, business_date)`, `(cheque_status)`.

### DB-PUR-006 SupplierPaymentAllocation
`payment_id`, `purchase_id`, `amount` num(14,2) > 0; unique `(payment_id, purchase_id)`; Σ per payment ≤ payment amount; Σ per purchase ≤ outstanding (service-checked under lock).

### DB-PUR-007 PurchaseReturn
`number` `DBN-…`, `purchase_id`, `supplier_id`, `branch_id`, `business_date`, `reason_code` enum(DAMAGED/EXPIRED/NEAR_EXPIRY_AGREEMENT/WRONG_ITEM/OVER_SUPPLY), `status` DRAFT/CONFIRMED/REVERSED, `pickup_status` PENDING_PICKUP/COLLECTED, `subtotal`, `vat_total`, `grand_total`, `confirmed_at/by`, `reversal_of_id`, `idempotency_key`.
**Rules:** stock decreases at CONFIRMED (BR-PUR-010); payable ↓ or supplier advance per supplier setting (BR-PUR-008).

### DB-PUR-008 PurchaseReturnItem
`return_id`, `purchase_item_id`, `batch_id`, `qty`, `unit_cost`, `vat_amount`, `line_total`; check `qty ≤ purchased − already returned` (service + constraint); all returns link to batch for traceability.

---

## Entity ↔ Use Case Map (this file)

| Entity | Primary UCs |
|---|---|
| MedicineBatch | UC-BATCH-001…003, UC-INV-002 |
| InventoryTransaction, StockBalance | UC-INV-001…005, UC-ADJ-003 |
| StockAdjustment(+Item) | UC-ADJ-001…003 |
| DocumentSequence | UC-SET-001 (all confirms) |
| Supplier, SupplierLedgerEntry | UC-SUP-001…003, UC-PPAY-001 |
| Purchase, PurchaseItem | UC-PUR-001…004, UC-BATCH-001 |
| SupplierPayment(+Allocation) | UC-PPAY-001…003 |
| PurchaseReturn(+Item) | UC-PRET-001/002 |
