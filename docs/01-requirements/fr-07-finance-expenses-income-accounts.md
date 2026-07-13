# Functional Requirements — Finance: Expenses, Income, Accounts, Receivables/Payables & Profit

**Document ID:** DOC-FR-07
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-EXP — Expenses

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-EXP-001 | Expense category CRUD seeded with common defaults (rent, utilities, transport, packaging, marketing, doctor samples, repairs, miscellaneous) | Acct | M | Used categories cannot be deleted, only deactivated |
| FR-EXP-002 | Expense entry: date, branch, category, amount, payment account, payee, reference, notes, attachment | Acct | M | Amount > 0; account required |
| FR-EXP-003 | Posting: entries above the configured threshold require approval (dual control); others post immediately | BM/Adm | M | Pending state blocks account impact until approved |
| FR-EXP-004 | Expenses immediately post an account transaction and appear in P&L | Sys | M | Account balance and P&L reflect the expense |
| FR-EXP-005 | Expense reversal (compensating entry) with permission and reason; period lock applies | Acct/Owner | M | Original retained; reversal linked |
| FR-EXP-006 | Expense list with filters (date range, category, branch, account, amount, status, payee) and export | Acct | M | Composable filters |
| FR-EXP-007 | Expense report by category/period/branch with totals and trend | BM | M | Matches entries |
| FR-EXP-008 | Attachment support via presigned object storage | Acct | S | Type/size validated |
| FR-EXP-009 | Edit allowed only while pending; posted expenses correct via reversal + new entry | Sys | M | API enforces |
| FR-EXP-010 | Recurring expense templates (e.g., monthly rent) with generated drafts | Acct | P2 | Not scheduled |
| FR-EXP-011 | Budget vs actual per category/period | BM | P2 | Not scheduled |
| FR-EXP-012 | Full audit of creation, approval, posting, reversal | Sys | M | Immutable entries |

## FR-INC — Other Income

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-INC-001 | Income category CRUD (seeded: commission, service income, scrap sales, rent income, miscellaneous) | Acct | M | Used categories deactivate only |
| FR-INC-002 | Income entry: date, branch, category, amount, account, source/payer, reference, notes | Acct | M | Amount > 0; account required |
| FR-INC-003 | Income posts immediately as an account transaction | Sys | M | Account balance and P&L reflect it |
| FR-INC-004 | Reversal with permission and reason; original retained | Acct/Owner | M | Linked compensating entry |
| FR-INC-005 | Income list with filters and export | Acct | M | Composable |
| FR-INC-006 | Income report by category/period/branch | BM | M | Matches entries |
| FR-INC-007 | Attachment support | Acct | S | Validated upload |
| FR-INC-008 | Full audit | Sys | M | Immutable entries |

## FR-FIN — Financial Accounts, Ledgers, Receivables, Payables & Profit

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-FIN-001 | Financial account CRUD: type (cash / bank / MFS wallet), name, branch, account number/provider, opening balance | Owner/Acct | M | Opening posts an `OPENING` transaction |
| FR-FIN-002 | Account balance is derived from transactions, cached transactionally, and rebuildable/reconciled | Sys | M | Nightly reconciliation; mismatches alerted |
| FR-FIN-003 | Append-only account transaction ledger: opening, sale receipt, purchase payment, expense, income, transfer in/out, adjustment, refund | Sys | M | No update/delete paths |
| FR-FIN-004 | Manual deposit/withdrawal with type, reason, and permission | Acct | M | Audited; source document optional but recorded |
| FR-FIN-005 | Account transfer between two accounts as a linked pair with the same transfer reference | Acct | M | Both entries post atomically; net zero |
| FR-FIN-006 | Account statement (date range) with running balance; print/PDF/Excel | Acct | M | Reconciles with transactions |
| FR-FIN-007 | Accounts scoped per branch; company-level accounts usable by permitted roles across branches | Owner | M | Postings respect branch scope |
| FR-FIN-008 | Negative balance prevention on accounts unless `allow_negative` is enabled for the account | Sys | M | `INSUFFICIENT_FUNDS` error otherwise (Q-033) |
| FR-FIN-009 | Customer receivables report (outstanding by customer) | Acct | M | Matches customer ledger caches |
| FR-FIN-010 | Supplier payables report (outstanding by supplier) | Acct | M | Matches supplier ledger caches |
| FR-FIN-011 | AR aging buckets with drill-down | Acct | M | Current, 1–30, 31–60, 61–90, 90+ |
| FR-FIN-012 | AP aging buckets with drill-down | Acct | M | Same buckets |
| FR-FIN-013 | Gross profit report: net revenue − COGS (batch actual cost), by invoice/item/category/branch/period | Acct/BM | M | COGS includes return reversals; discounts reduce revenue |
| FR-FIN-014 | Net profit = gross profit − expenses + other income, per period/branch, with comparison to prior period | Owner | M | Matches P&L components |
| FR-FIN-015 | COGS computed from stock ledger batch costs at sale/return time (no recalculation of history) | Sys | M | Report reconciles to ledger |
| FR-FIN-016 | Discount impact report (line/invoice discounts by user, period, customer) | Owner | M | Ties to invoice data |
| FR-FIN-017 | Output VAT (sales) summary per period with rate breakup | Acct | M | Matches sales register |
| FR-FIN-018 | Input VAT (purchases) summary per period | Acct | M | Matches purchase register |
| FR-FIN-019 | Net VAT position report (output − input) per period with drill-down | Acct | M | Feeds VAT filing preparation (not automated filing) |
| FR-FIN-020 | Ledger reconciliation report: cached balances vs ledger sums for customers, suppliers, accounts, stock | Sys/Acct | M | Lists discrepancies with deltas; repair task |
| FR-FIN-021 | Period close/lock: lock a fiscal month after close; reopen only by Owner with reason and audit | Owner | M | Postings into locked months blocked (`PERIOD_LOCKED`) |
| FR-FIN-022 | Opening balance tooling: accounts, customers, suppliers, stock via `OPENING` entries (go-live import) | Acct | M | Opening date configurable; reports show opening separately |
| FR-FIN-023 | Account transfer above threshold requires approval | Owner | S | Pending approval state |
| FR-FIN-024 | Cheque register: all cheque receipts/payments with status and aging of pending cheques | Acct | S | Matches payment records |
| FR-FIN-025 | Daily funds position: balances across all accounts per branch, consolidated for Owner | Owner/BM | M | Matches account balances |
| FR-FIN-026 | Account posting permissions: per-account role restrictions (e.g., only Accountant posts to bank) | SA | S | Enforced server-side |
| FR-FIN-027 | P&L comparison across periods and branches with export | Owner | M | Numbers reconcile with FR-FIN-013/014 |
| FR-FIN-028 | Financial dashboard widgets: today's collection, dues, payables, cash position, profit MTD | Owner/BM | M | Values match reports |
| FR-FIN-029 | Audit of every financial posting, reversal, and period action | Sys | M | Immutable entries |
| FR-FIN-030 | Export all financial reports to Excel/PDF honoring filters | Acct | M | Totals match on-screen |

---

*Cross-references: BR-FIN-001…009 in `docs/01-requirements/08-business-rules.md`; DEC-002 (no GL in MVP).*
