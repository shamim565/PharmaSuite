# Entity Catalog 3 — Customers, Sales, Payments & Sales Returns

**Document ID:** DOC-ENT-03
**Parent:** `docs/03-domain-model.md`
**Conventions:** see `entities-01`. Status dimensions per `state-machines.md` §1; ledgers append-only.

---

### DB-SALE-001 Customer
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(20) | ✔ | Unique among non-deleted |
| `name` | txt(200) | ✔ | Indexed (trigram search) |
| `customer_type` | enum | ✔ | PHARMACY / RETAIL / HOSPITAL / CLINIC |
| `contact_person`, `phone`, `email`, `address` | txt | ○ | |
| `area` / `territory_id` | txt/fk→Territory | ○ | Territory feeds rep reports |
| `price_tier` | enum | ✔ | RETAIL / WHOLESALE / CUSTOM (A-018) |
| `default_discount_pct` | num(5,2) | ○ | Pre-fills lines (FR-CUST-020) |
| `credit_limit` | num(14,2) | ✔ | 0 = cash only |
| `credit_days` | int | ✔ | 0 = due on invoice date |
| `credit_hold` | bool | ✔ | Blocks new credit sales (`CUSTOMER_ON_HOLD`) |
| `credit_hold_reason` | txt | ○ | |
| `default_rep_id` | fk→Representative | ○ | Defaults onto invoices |
| `balance_cache` | num(14,2) | ✔ | Receivable; derived + reconciled |
| `status` | enum | ✔ | ACTIVE / INACTIVE |
| `notes` | txt | ○ | |
**Relationships:** 1:N CustomerLedgerEntry, SalesInvoice, Payment, SalesReturn; N:1 Territory/Representative.
**Soft delete:** deactivate with history; duplicate merge blocked when both have transactions.

### DB-SALE-002 CustomerLedgerEntry *(append-only)*
`entry_type` (OPENING, INVOICE, PAYMENT, PAYMENT_REVERSAL, SALES_RETURN, RETURN_REVERSAL, ADVANCE_APPLIED, ADVANCE_REFUND, WRITE_OFF, ADJUSTMENT), `amount_delta` num(14,2), `due_date` date ○ (invoices), `source_type/id/number`, `transaction_group_id`, `reverses_entry_id`, `idempotency_key`, `business_date`, `seq`.
**Indexes:** `(customer_id, seq)`, `(customer_id, due_date)`, `(source_type, source_id)`.

### DB-SALE-003 SalesInvoice
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ○ | `INV-…` at confirm; unique `(branch, fy, number)`; retained as VOID on cancel |
| `customer_id`, `branch_id`, `business_date` | | ✔ | Walk-in pseudo-customer only if feature flag (BR-SALE-001) |
| `sales_rep_id` | fk→Representative | ○ | Attribution (BR-CRM-003) |
| `doctor_id` | fk→Doctor | ○ | Invoice-level influence attribution |
| `lifecycle` | enum | ✔ | DRAFT / CONFIRMED / CANCELLED |
| `payment_status` | enum | ✔ | UNPAID / PARTIALLY_PAID / PAID |
| `return_status` | enum | ✔ | NONE / PARTIALLY_RETURNED / FULLY_RETURNED |
| `fulfillment_status` | enum | ✔ | PENDING / DELIVERED |
| `delivered_at`, `delivered_by` | ts/fk→User | ○ | Lightweight delivery tracking (Q-023) |
| `subtotal`, `discount_total`, `vat_total`, `round_off`, `grand_total` | num(14,2) | ✔ | Server-computed (BR-SALE-007) |
| `paid_total`, `returned_total` | num(14,2) | ✔ | Caches from allocations/returns |
| `due_date` | date | ✔ | `business_date + customer.credit_days` |
| `rx_reference` | txt | ○ | Per policy |
| `notes`, `delivery_address` | txt | ○ | |
| `override_metadata` | jsonb | ○ | credit / below-cost / FEFO / free-goods flags + reason + actor + permission |
| `confirmed_at/by`, `cancel_reason`, `reversal_group_id` | | ○ | |
| `idempotency_key` | txt | ○ | Unique for confirm |
**Indexes:** `(branch_id, business_date)`, `(customer_id, business_date)`, `(customer_id, due_date)`, `(sales_rep_id, business_date)`, `(doctor_id)`, partial `(payment_status) WHERE payment_status <> 'PAID'`, partial `(return_status) WHERE return_status <> 'NONE'`.
**Rules:** confirmed invoice immutable; cancellation only when unpaid/unreturned (BR-SALE-008/009); all overrides recorded for the Exception Report.

### DB-SALE-004 SalesInvoiceItem
| Field | Type | Req | Rules |
|---|---|---|---|
| `invoice_id`, `line_no` | | ✔ | Unique `(invoice_id, line_no)` |
| `medicine_id`, `batch_id` | fk | ✔ | **One line = one batch** (A-012, EC-001) |
| `entry_unit_id`, `qty_entered`, `conversion_factor`, `qty_base` | | ✔ | Base units are authoritative |
| `unit_price` | num(14,4) | ✔ | Tier price or override (audited) |
| `line_discount_pct`, `line_discount_amount` | num(5,2)/num(14,2) | ○ | Discount guard per role |
| `invoice_discount_share` | num(14,2) | ○ | Pro-rata allocation (BR-SALE-007) |
| `vat_rate`, `vat_amount` | num(5,2)/num(14,2) | ✔ | On discounted net |
| `line_net` | num(14,2) | ✔ | Rounded half-up |
| `unit_cost` | num(14,4) | ✔ | Batch cost snapshot at confirm (COGS basis) |
| `doctor_id` | fk→Doctor | ○ | Per-line influence attribution |
| `is_free_goods` | bool | ✔ | Zero-price lines (BR-SALE-014) |
| `scheme_code` | txt | ○ | Applied buy-X-get-Y scheme (BR-SALE-015) |
**Indexes:** `(invoice_id)`, `(medicine_id)`, `(batch_id)`, `(doctor_id)`.

### DB-SALE-005 Payment
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ✔ | `RCP-…` gapless |
| `customer_id`, `branch_id`, `business_date` | | ✔ | |
| `amount` | num(14,2) | ✔ | > 0; equals Σ method lines |
| `collector_user_id` | fk→User | ✔ | Collection attribution |
| `status` | enum | ✔ | ACTIVE / REVERSED |
| `reversal_of_id`, `reversal_reason` | fk/txt | ○ | Compensating only |
| `idempotency_key` | txt | ✔ | Unique |
**Indexes:** `(customer_id, business_date)`, `(collector_user_id, business_date)`, `(status)`.

### DB-SALE-009 PaymentMethodLine
| Field | Type | Req | Rules |
|---|---|---|---|
| `payment_id` | fk→Payment | ✔ | 1..N lines per payment (split methods) |
| `method` | enum | ✔ | CASH / BANK / MFS / CHEQUE / ADVANCE_APPLIED |
| `account_id` | fk→FinancialAccount | ✔ | Method→account mapping (BR-PAY-003) |
| `amount` | num(14,2) | ✔ | > 0 |
| `reference`, `cheque_no`, `cheque_date`, `cheque_status` | txt/date/enum | ○ | PENDING/CLEARED/BOUNCED |
**Rules:** Σ lines = payment amount (service + trigger); each line posts one FinancialTransaction.

### DB-SALE-006 PaymentAllocation
`payment_id`, `invoice_id`, `amount` num(14,2) > 0; unique `(payment_id, invoice_id)`; per-invoice Σ ≤ outstanding and per-payment Σ ≤ amount enforced in the allocation service under invoice/customer locks (BR-PAY-002).

### DB-SALE-007 SalesReturn
| Field | Type | Req | Rules |
|---|---|---|---|
| `number` | txt | ○ | `CRN-…` at confirm |
| `invoice_id` | fk→SalesInvoice | ○ | Null only for no-invoice returns with permission (BR-SRET-006) |
| `customer_id`, `branch_id`, `business_date` | | ✔ | |
| `reason_code` | enum | ✔ | CUSTOMER_RETURN / DAMAGED / EXPIRED_AT_CUSTOMER / WRONG_ITEM / EXCESS_SUPPLY |
| `status` | enum | ✔ | DRAFT / CONFIRMED / REVERSED |
| `refund_method` | enum | ✔ | CUSTOMER_CREDIT (default) / CASH / BANK / ADJUST_DUES |
| `refund_account_id` | fk→FinancialAccount | ○ | Required for CASH/BANK; `RETURN_REFUND` permission |
| `subtotal`, `discount_reversal`, `vat_reversal`, `grand_total` | num(14,2) | ✔ | Proportional reversal (BR-SRET-003/007) |
| `is_no_invoice` | bool | ✔ | Exception-flagged |
| `confirmed_at/by`, `reversal_of_id`, `idempotency_key` | | ○/✔ | |
**Indexes:** `(customer_id, business_date)`, `(invoice_id)`, `(branch_id, business_date)`.

### DB-SALE-008 SalesReturnItem
`return_id`, `invoice_item_id` (nullable for no-invoice), `batch_id`, `medicine_id`, `qty`, `condition` enum(RESELLABLE/DAMAGED/EXPIRED), `unit_price`, `discount_reversal_share`, `vat_amount`, `unit_cost` (original batch cost), `restock` bool (derived from condition + expiry).
**Rules:** qty ≤ sold − returned; RESELLABLE+non-expired → restock original batch; else QUARANTINE pool, zero saleable impact (BR-SRET-002); COGS reversal at original cost (BR-SRET-003); bonus returns handled per BR-SRET-008.

---

## Entity ↔ Use Case Map (this file)

| Entity | Primary UCs |
|---|---|
| Customer, CustomerLedgerEntry | UC-CUST-001…003, UC-PAY-001/004 |
| SalesInvoice(+Item) | UC-SALE-001…006, UC-CUST-002 |
| Payment, PaymentMethodLine, PaymentAllocation | UC-PAY-001…006, UC-SALE-006 |
| SalesReturn(+Item) | UC-SRET-001…003, UC-PAY-003 (reversal links) |
