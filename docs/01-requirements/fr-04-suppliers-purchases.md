# Functional Requirements — Suppliers, Purchases, Purchase Payments & Returns

**Document ID:** DOC-FR-04
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-SUP — Suppliers & Supplier Ledger

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-SUP-001 | Supplier CRUD: name, unique code, supplier type (manufacturer/importer/trader), address, phones, email, contact person | WM/Acct | M | Duplicate code rejected |
| FR-SUP-002 | Store tax/legal details: BIN/VAT number, trade license, terms | Acct | M | Used on debit notes/reports |
| FR-SUP-003 | Payment terms per supplier: credit days default, preferred payment method | Acct | M | Pre-fills on purchase/payment entry |
| FR-SUP-004 | Opening payable balance entry per supplier as an `OPENING` ledger entry (go-live import) | Acct | M | Appears in ledger and aging as opening item |
| FR-SUP-005 | Append-only supplier ledger with document-level drill-down (purchase, payment, return, adjustment, opening) | Acct | M | Balance equals Σ entries; cache reconciled nightly |
| FR-SUP-006 | Supplier statement (date range) with opening balance, movements, closing balance; print/PDF/Excel | Acct | M | Reconciles exactly with ledger |
| FR-SUP-007 | Payable balance per supplier and consolidated across suppliers | Acct/BM | M | Filters by branch/company; matches aging total |
| FR-SUP-008 | Payable aging buckets: current, 1–30, 31–60, 61–90, 90+ days | Acct | M | Drill-down to invoices per bucket |
| FR-SUP-009 | Supplier list with search (name/code/phone/BIN) and filters (status, type, balance) | All | M | Export available |
| FR-SUP-010 | Activate/deactivate suppliers; deletion blocked when transactions exist (soft delete only) | Adm | M | Deactivated supplier cannot be selected on new documents |
| FR-SUP-011 | Duplicate warning on create/edit when name, phone or BIN matches an existing supplier | Sys | S | Warning allows proceed with confirmation and audit |
| FR-SUP-012 | Multiple contact persons per supplier with roles/phones | WM | S | Primary contact flagged |
| FR-SUP-013 | Bank account details for supplier payments | Acct | M | Masked from roles without payment permission |
| FR-SUP-014 | Attachments (trade license, agreements) via presigned object-storage upload | Adm | S | Type/size validated (A-026) |
| FR-SUP-015 | Supplier detail tabs: profile, ledger, purchases, payments, returns, attachments | All | M | Tabs respect permissions |
| FR-SUP-016 | Supplier return summary with debit notes | Acct | M | Links to purchase return documents |
| FR-SUP-017 | Supplier payable adjustment/write-off entry with permission and reason (audited) | Acct | S | Appears in ledger with adjustment type |
| FR-SUP-018 | Merge duplicate suppliers blocked when both have transactions | Adm | S | Otherwise remaps references and deactivates duplicate; audited |

## FR-PUR — Purchases (Goods Receipt)

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-PUR-001 | Create draft purchase: supplier, branch, supplier invoice no. & date, purchase date, notes, attachments | WM | M | Draft freely editable; no stock effect |
| FR-PUR-002 | Line entry: medicine, batch number, mfg date, expiry, quantity (entry unit), bonus quantity, unit cost, line discount, VAT rate/amount | WM | M | Invalid fields rejected; expiry mandatory for medicine items |
| FR-PUR-003 | Exactly one batch per purchase line (medicine + batch + expiry) | Sys | M | Duplicate batch line in one purchase for same medicine merges or warns |
| FR-PUR-004 | Live totals: subtotal, line/invoice discounts, VAT, round-off, grand total, amount payable now | WM | M | Totals update as lines change and match printed document |
| FR-PUR-005 | Entry in any allowed purchase unit; system converts to base units for stock | WM | M | Base qty = entry qty × conversion factor, exact |
| FR-PUR-006 | Duplicate supplier invoice detection (same supplier + invoice number) blocks confirmation; `PUR_DUP_INVOICE` override with reason | Sys | M | Override audited and reported |
| FR-PUR-007 | Purchases editable only in DRAFT; confirmed purchases are immutable | Sys | M | API rejects edits to confirmed purchases |
| FR-PUR-008 | Confirm purchase atomically: create/merge batches, post stock movements, post supplier payable, post account transaction for any immediate payment, allocate purchase number | Sys | M | Partial failure rolls back everything; number never leaks |
| FR-PUR-009 | Payment at entry: none (credit), partial, or full; multiple methods allowed | WM/Acct | M | Payable updated correctly in all cases |
| FR-PUR-010 | Purchase numbering gapless per branch/fiscal year: `PUR-{BRANCH}-{YY}-{000001}` (format configurable, Q-017) | Sys | M | Sequence allocated inside the transaction (A-014) |
| FR-PUR-011 | Attach supplier invoice image/PDF at header level | WM | M | Stored via object storage; visible from purchase detail |
| FR-PUR-012 | Print purchase voucher/summary PDF (A4) with all lines, batches, totals | WM | M | Matches system data |
| FR-PUR-013 | Cancel draft freely; cancelling a confirmed purchase allowed only when no payments and no returns, via reversal postings; otherwise use purchase return | Adm | M | Originals retained; reversal linked and audited |
| FR-PUR-014 | Per-line margin preview (selling price vs effective cost) where user has `VIEW_COST` | WM/Adm | S | Hidden entirely without permission |
| FR-PUR-015 | Effective unit cost computed and shown, with bonus allocation applied (`net line ÷ (qty + bonus)`) | Sys | M | Stored on batch; used for COGS (DEC-008) |
| FR-PUR-016 | Purchase list filters: date range, supplier, branch, status, amount, medicine, batch number | All | M | Composable; exportable |
| FR-PUR-017 | Purchase detail with batch, payment and return links and full audit history | All | M | Permission-aware sections |
| FR-PUR-018 | Payments tab showing allocated/unallocated amounts and balance due per purchase | Acct | M | Matches supplier ledger |
| FR-PUR-019 | Freight/other charges at header or line level allocated to cost by value (landed cost) | WM/Acct | S | Effective cost includes allocation; visible in breakdown |
| FR-PUR-020 | Purchase VAT captured per line for input-tax reporting | Sys | M | VAT summary report reconciles |
| FR-PUR-021 | Due-date preview from supplier credit days when entering credit purchase | Acct | S | Shown on purchase and payable aging |
| FR-PUR-022 | Backdating allowed only within open periods and with `DOC_BACKDATE`; period lock always enforced | Adm | M | Attempts into locked months fail with `PERIOD_LOCKED` |
| FR-PUR-023 | Idempotency: duplicate confirm requests with same key return the same purchase | Sys | M | No duplicate stock/payable |
| FR-PUR-024 | Search purchases by supplier invoice number and batch number | All | M | Results link to purchase detail |
| FR-PUR-025 | Configurable high-value purchase approval: above threshold requires approval before confirmation | Adm/Owner | P2 | Not scheduled |
| FR-PUR-026 | Provide an "unpaid purchases" quick view per supplier (open bills) | Acct | M | Feeds payment allocation screen |
| FR-PUR-027 | Show current batch stock and expiry for the medicine being purchased (duplicate-batch awareness) | WM | S | Helps avoid accidental duplicate batch entries |
| FR-PUR-028 | Warn when purchase unit cost exceeds a configurable % above last purchase cost | Sys | S | Warning; override audited if permitted |
| FR-PUR-029 | Purchase reports: register, by supplier, by item, by category, VAT input summary (see FR-RPT) | Acct | M | Cross-linked in reports module |
| FR-PUR-030 | Full lifecycle audit: draft edits, confirmation, edits blocked, cancellation, attachments | Sys | M | Audit entries immutable |

## FR-PPAY — Purchase (Supplier) Payments

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-PPAY-001 | Record supplier payment: supplier, branch, date, amount, method(s), financial account, reference, note | Acct | M | Validation against account balance rules (BR-FIN-008) |
| FR-PPAY-002 | Allocate payment to one or more purchases; FIFO default, manual allocation allowed; partial allocations supported | Acct | M | Σ allocations ≤ payment amount; purchase balances update |
| FR-PPAY-003 | Unallocated excess recorded as supplier advance (or blocked, per Q-026 default block unless explicitly advance) | Acct | M | Advance visible on supplier account |
| FR-PPAY-004 | Reverse a payment with permission and reason; restores allocations, payable, purchase status, account balance | Acct/Adm | M | Original retained; reversal linked; cross-period reversals flagged |
| FR-PPAY-005 | Payment voucher numbering gapless: `PPV-{BRANCH}-{YY}-{000001}` | Sys | M | Allocated in transaction |
| FR-PPAY-006 | Methods: cash, bank transfer, MFS, cheque; each maps to a financial account | Acct | M | Account transaction posted per method |
| FR-PPAY-007 | Cheque lifecycle: pending → cleared → bounced; bounce reverses allocation and re-opens purchases | Acct | S | Status changes audited; bounced cheques reported |
| FR-PPAY-008 | Payment list with filters (date, supplier, method, amount, branch) and export | Acct | M | Totals reconcile with account movements |
| FR-PPAY-009 | Purchase status reflects PAID / PARTIALLY_PAID / UNPAID basis on allocations | Sys | M | Status updates on allocation/reversal |
| FR-PPAY-010 | Idempotency and audit on all payment POSTs | Sys | M | Duplicate submission returns original voucher |

## FR-PRET — Purchase Returns (Debit Notes)

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-PRET-001 | Create return from a confirmed purchase; select lines/batches and quantities not exceeding returnable quantity (purchased − already returned) | WM | M | Over-return blocked with remaining quantity shown |
| FR-PRET-002 | Mandatory return reason: damaged, expired, near-expiry agreement, wrong item, over-supply | WM | M | Report groups by reason |
| FR-PRET-003 | Return always reduces batch stock on confirmation (goods leave the warehouse); destination condition recorded (returned to supplier / pending pickup) | Sys/WM | M | Stock and batch balances decrease correctly |
| FR-PRET-004 | Debit note numbering `DBN-{BRANCH}-{YY}-{000001}`; value includes proportional VAT reversal | Sys | M | VAT summary reconciles |
| FR-PRET-005 | Financial effect: reduce supplier payable; if payable would go below zero, excess becomes supplier advance/receivable (per supplier setting) | Acct | M | Ledger shows correct movement |
| FR-PRET-006 | Confirmed returns are immutable; corrections via compensating reversal | Sys | M | Edit API blocked |
| FR-PRET-007 | Link return lines to original purchase line and batch for traceability | Sys | M | Trace report shows purchase ↔ return chain |
| FR-PRET-008 | Print debit note PDF | WM | M | Matches system data |
| FR-PRET-009 | Return list with filters (date, supplier, branch, item) and export | Acct | M | Composable filters |
| FR-PRET-010 | Batch may become depleted after return; batch status updates automatically | Sys | M | Depleted batches cannot be sold |
| FR-PRET-011 | Period lock and backdating rules apply | Sys | M | `PERIOD_LOCKED` on locked months |
| FR-PRET-012 | Purchase status reflects partial/full return | Sys | M | Detail view shows returned quantities |
| FR-PRET-013 | Idempotency and full audit | Sys | M | Duplicate submission returns original debit note |
| FR-PRET-014 | Pending-pickup view: returns not yet collected by supplier listed for follow-up | WM | S | Ageing of pending pickups reported |

---

*Cross-references: BR-PUR-001…010, BR-FIN-* in `docs/01-requirements/08-business-rules.md`.*
