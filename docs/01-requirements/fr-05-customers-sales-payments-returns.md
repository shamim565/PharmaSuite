# Functional Requirements — Customers, Sales, Payments & Sales Returns

**Document ID:** DOC-FR-05
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-CUST — Customers & Customer Ledger

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-CUST-001 | Customer CRUD: name, unique code, type (pharmacy/retail/hospital/clinic), contacts, address, area/territory | SO/Adm | M | Duplicate code rejected |
| FR-CUST-002 | Credit limit (BDT) and credit days per customer | Adm/Acct | M | Used by credit control (BR-SALE-005) |
| FR-CUST-003 | Price tier assignment: retail / wholesale / custom | Adm | M | Invoice line prices resolve by tier |
| FR-CUST-004 | Opening receivable entry as `OPENING` ledger entry | Acct | M | Appears in aging as opening balance |
| FR-CUST-005 | Append-only customer ledger with per-document drill-down (invoice, payment, return, adjustment, opening) | Acct | M | Balance = Σ entries; cache reconciled nightly |
| FR-CUST-006 | Customer statement (date range) with opening balance, movements, closing; print/PDF/Excel | Acct | M | Reconciles exactly with ledger |
| FR-CUST-007 | Receivable balance and aging (current, 1–30, 31–60, 61–90, 90+ days) | Acct/BM | M | Drill-down to documents per bucket |
| FR-CUST-008 | Customer list search (name/code/phone) and filters (area, tier, status, balance, assigned rep, overdue) | All | M | Exportable |
| FR-CUST-009 | Activate/deactivate; deletion soft-only once transactions exist | Adm | M | Deactivated customer excluded from new invoices |
| FR-CUST-010 | Duplicate warning on create/edit (name/phone/address match) | Sys | S | Proceed with confirmation; audited |
| FR-CUST-011 | Multiple contact persons per customer | SO | S | Primary contact flagged |
| FR-CUST-012 | Assign sales representative per customer (defaults onto invoices) | BM | M | Rep-wise sales reports use this link |
| FR-CUST-013 | Attachments (trade license/agreement) via presigned object storage | Adm | S | Type/size validated |
| FR-CUST-014 | Customer detail tabs: profile, ledger, invoices, payments, returns, visits | All | M | Permissions applied per tab |
| FR-CUST-015 | "Collect due" quick action from customer row/list opens collection sheet pre-filled | Acct/SO | M | Payment posts against that customer only |
| FR-CUST-016 | Advance/on-account balance visible on profile and at invoice entry | Acct | M | Auto-apply respects FR-PAY-018 |
| FR-CUST-017 | Credit hold/blacklist flag blocks new credit sales until cleared by authorized role | Acct/BM | M | Blocked invoice returns `CUSTOMER_ON_HOLD` |
| FR-CUST-018 | Merge duplicate customers blocked when both have transactions | Adm | S | Otherwise remaps and deactivates duplicate; audited |
| FR-CUST-019 | Capture geo-location for customer address (map pin) | SO | P2 | Not scheduled |
| FR-CUST-020 | Customer category drives default tier and default discount % | Adm | S | Defaults pre-fill invoice lines |

## FR-SALE — Sales & Invoices

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-SALE-001 | Create draft invoice: customer, branch, date, sales rep, delivery address/date, notes | SO | M | Draft has no stock/ledger effect |
| FR-SALE-002 | Add lines via search (name/generic/code/barcode-ready): medicine, batch, quantity (sale unit), unit price, line discount, VAT | SO | M | Invalid/absent fields blocked with field errors |
| FR-SALE-003 | FEFO auto-selects saleable batches; manual override requires `INV_OVERRIDE_FEFO` + reason | SO/BM | M | Preselection deterministic; override audited |
| FR-SALE-004 | Live availability check: cannot add/save quantity beyond available saleable stock | Sys | M | Server re-validates at confirmation |
| FR-SALE-005 | Price resolves from customer tier; manual price edit requires permission; below-cost guard applies (BR-SALE-006) | SO/BM | M | Overrides audited and reported |
| FR-SALE-006 | Line discount (%/amount) and invoice-level discount (amount) allocated pro-rata to lines for VAT/margin | SO | M | Invoice and line totals reconcile to the paisa |
| FR-SALE-007 | VAT computed per line on discounted net value at medicine rate | Sys | M | VAT summary reconciles |
| FR-SALE-008 | Round-off line adjusts grand total to nearest whole BDT (configurable, max ±0.50) | Sys | M | Printed total equals computed total |
| FR-SALE-009 | Credit control: credit limit and overdue checks with `SALE_OVERRIDE_CREDIT` override + reason (BR-SALE-005) | Sys/BM | M | Overrides audited and reported |
| FR-SALE-010 | Payment at entry: full/partial, single or split methods; immediate receipt created and linked | SO/Acct | M | Invoice payment status correct immediately |
| FR-SALE-011 | Optional doctor reference per line/invoice for promoted-medicine attribution | SO | M | Doctor-wise sales reports populate |
| FR-SALE-012 | Sales representative attribution stored on invoice (default from customer) | Sys | M | Rep performance reports populate |
| FR-SALE-013 | Capture Rx reference for prescription-required items per company policy (warn/require/off) | SO | S | Policy enforced consistently at API level |
| FR-SALE-014 | Drafts freely editable/deletable; no stock, ledger or number effects | SO | M | Confirm is the only commitment point |
| FR-SALE-015 | Confirm atomically: allocate invoice number, deduct FEFO batch stock, post stock ledger, post customer receivable (grand total), post account transaction for paid amount, set payment status | Sys | M | Any failure rolls back all effects; no partial invoices |
| FR-SALE-016 | Invoice numbering gapless per branch/fiscal year `INV-{BRANCH}-{YY}-{000001}` (format configurable) | Sys | M | Allocated inside transaction; reprint keeps same number |
| FR-SALE-017 | Idempotency-Key required on confirm; replay returns the same invoice | Sys | M | Double-tap/retry cannot create two invoices |
| FR-SALE-018 | Cancel rules: allowed only when no payments and no returns; cancel is a reversal (stock, ledger, numbers retained as void) | Adm | M | Cancelled invoice visible with CANCELLED status and reason |
| FR-SALE-019 | Invoices with any payment or return cannot be cancelled; corrections via sales return/credit note | Sys | M | Error suggests the correct path |
| FR-SALE-020 | Print invoice PDF (A4/A5 templates, configured copies, VAT fields, control-class warnings) | SO | M | Matches system data exactly |
| FR-SALE-021 | Reprint adds REPRINT watermark and is audited | Sys | M | Reprint count visible in detail |
| FR-SALE-022 | Share invoice PDF via native share (mobile) / download link; WhatsApp automation is Phase 2 | SO | M | Shared file matches current invoice state |
| FR-SALE-023 | Invoice list filters: date, customer, branch, status, payment status, amount, rep, doctor, batch | All | M | Composable, URL-shareable, exportable |
| FR-SALE-024 | Invoice detail: lines with batches, payments, returns, delivery info, audit trail, print/share | All | M | All sections permission-aware |
| FR-SALE-025 | Payment status transitions: CONFIRMED → PARTIALLY_PAID → PAID (and return variants) | Sys | M | Status always matches allocations |
| FR-SALE-026 | Due amount and due date (invoice date + credit days) shown on invoice and due reports | Sys | M | Aging uses due date |
| FR-SALE-027 | Backdating within open periods with `DOC_BACKDATE`; period lock enforced | Adm | M | Locked period returns `PERIOD_LOCKED` |
| FR-SALE-028 | Approaching credit limit warning at entry (e.g., ≥ 80% utilized) | Sys | S | Warning shown; no block |
| FR-SALE-029 | Zero-value/replacement invoice allowed only with `SALE_ZERO_VALUE`; flagged in reports | Adm | S | Audited; appears in exception report |
| FR-SALE-030 | Price override below tier price allowed with `SALE_PRICE_OVERRIDE` (still subject to below-cost guard) | BM | M | Audited and reportable |
| FR-SALE-031 | Duplicate previous invoice action: copy lines from a chosen invoice for the same customer into a new draft | SO | S | New draft only; prices re-resolved |
| FR-SALE-032 | Parked drafts with labels for later completion (per user) | SO | S | Parked list per user; no stock effect |
| FR-SALE-033 | Delivery tracking: status pending/delivered, delivered by/at, updated from invoice or list | SO/WM | S | Delivered invoices filterable |
| FR-SALE-034 | Sales bonus scheme: configurable buy-X-get-Y free-goods suggestion adds a zero-price bonus line with stock deduction | Sys | S | Scheme is explicit on the invoice; stock balances correct |
| FR-SALE-035 | Manual free-goods line requires `SALE_FREE_GOODS`; appears in exception report | Adm | S | Audited |
| FR-SALE-036 | Export invoice list and sales register to Excel/PDF honoring filters | Acct | M | Totals match on-screen |
| FR-SALE-037 | All invoice lifecycle events audited (draft, confirm, reprint, cancel, overrides) | Sys | M | Immutable audit entries |
| FR-SALE-038 | Sales register (day book) per branch/date with invoice-level detail | Acct | M | Feeds VAT summary and P&L |

## FR-PAY — Customer Payments, Due Collection & Allocation

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-PAY-001 | Collect payment: customer, date, amount, method(s) with split support, financial accounts, references, collector, notes | Acct/SO | M | Multiple methods sum exactly to payment amount |
| FR-PAY-002 | Automatic FIFO allocation to oldest due invoices by invoice date | Sys | M | Allocation order deterministic |
| FR-PAY-003 | Manual allocation/re-allocation across invoices with permission and audit | Acct | M | Re-allocation restores prior invoice statuses correctly |
| FR-PAY-004 | Partial payments supported; invoice status updates per allocation | Sys | M | Outstanding = grand total − allocated |
| FR-PAY-005 | Unallocated amount recorded as customer advance/on-account (per company policy) | Acct | M | Advance balance visible and reusable |
| FR-PAY-006 | Overpayment beyond total outstanding blocked for single-invoice collection unless explicitly recorded as advance (Q-026) | Sys | M | Error shows maximum allowed |
| FR-PAY-007 | Receipt numbering gapless `RCP-{BRANCH}-{YY}-{000001}` | Sys | M | Allocated in transaction |
| FR-PAY-008 | Receipt print (A5 / thermal-ready PDF) and share via native share/download | SO | M | Matches payment data |
| FR-PAY-009 | Reversal rules: same-day reversal by Accountant; cross-period reversal by Owner with reason; compensating entries only | Acct/Owner | M | Statuses restored; cross-period flagged in report |
| FR-PAY-010 | Payment list filters: date, customer, collector, method, amount, branch, cheque status | Acct | M | Exportable |
| FR-PAY-011 | Daily collection report grouped by collector, method, branch | Acct/BM | M | Sum matches payment entries for the day |
| FR-PAY-012 | Collector reconciliation: expected vs submitted cash per collector/day (simple) | Acct | S | Discrepancy highlighted |
| FR-PAY-013 | Cheque lifecycle: pending → cleared → bounced; bounce reverses allocations and re-opens invoices | Acct | S | Status history audited |
| FR-PAY-014 | Bank/MFS reference number mandatory for bank/MFS methods | Sys | M | Missing reference rejected |
| FR-PAY-015 | Payment history visible on customer and invoice screens | All | M | Respects permissions |
| FR-PAY-016 | Due list: all outstanding invoices with aging, customer, rep; quick-collect action | Acct/SO | M | Aging totals match FR-CUST-007 |
| FR-PAY-017 | Idempotency-Key on payment POST; duplicate submissions return the original receipt | Sys | M | No double collection |
| FR-PAY-018 | Auto-apply customer advance at invoice confirmation when enabled for that customer; otherwise manual | Sys | S | Applied amount shown on invoice |
| FR-PAY-019 | Allocation row locks prevent concurrent payment double-allocation on the same invoice | Sys | M | Concurrency tests pass (TC-PAY-…) |
| FR-PAY-020 | Full audit of payment creation, allocation, re-allocation, reversal | Sys | M | Immutable entries |

## FR-SRET — Sales Returns & Credit Notes

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-SRET-001 | Create return from original invoice; select lines and quantities ≤ sold − already returned | SO/BM | M | Over-return blocked with remaining quantity |
| FR-SRET-002 | Mandatory return reason: customer return, damaged, expired-at-customer, wrong item, excess supply | SO | M | Report groups by reason |
| FR-SRET-003 | Per-line condition: resellable / damaged / expired | WM | M | Drives restock decision |
| FR-SRET-004 | Restock resellable non-expired goods to the original batch via return movement; damaged/expired go to quarantine pool (no saleable stock) | Sys/WM | M | Stock math correct in both cases |
| FR-SRET-005 | Credit note numbering `CRN-{BRANCH}-{YY}-{000001}`; value includes proportional VAT and discount reversal | Sys | M | VAT summary reconciles |
| FR-SRET-006 | Refund method: customer credit (default) / cash / bank / adjust dues, each gate by `RETURN_REFUND` | Acct | M | Chosen method visible on credit note |
| FR-SRET-007 | Invoice status recomputed: PARTIALLY_RETURNED / FULLY_RETURNED | Sys | M | Status matches returned quantities |
| FR-SRET-008 | Return without original invoice only with `SRET_NO_INVOICE` (default off); such returns flagged in an exception report | Adm | S | Audited with reason |
| FR-SRET-009 | Confirmed returns immutable; reversal by compensating entry with permission | Adm | M | Original retained |
| FR-SRET-010 | Stock ledger and batch balances updated via return movements with original batch link | Sys | M | Batch traceability intact |
| FR-SRET-011 | Print credit note PDF | SO | M | Matches system data |
| FR-SRET-012 | Return list filters (date, customer, branch, item, reason) and export | All | M | Composable |
| FR-SRET-013 | Return value cannot exceed remaining invoice value (net of prior returns) | Sys | M | Validation error otherwise |
| FR-SRET-014 | Period lock and backdating rules apply | Sys | M | `PERIOD_LOCKED` enforced |
| FR-SRET-015 | Idempotency and full audit | Sys | M | Duplicate submission returns original credit note |
| FR-SRET-016 | Return of free/bonus goods reverses bonus stock as well | Sys | S | Bonus quantity returned to batch correctly |

---

*Cross-references: BR-SALE-*, BR-PAY-*, BR-SRET-* in `docs/01-requirements/08-business-rules.md`; concurrency and edge cases in Phase 2.*
