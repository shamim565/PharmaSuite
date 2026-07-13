# Functional Requirements — Reports, Dashboard, Search, Notifications, Audit & Settings

**Document ID:** DOC-FR-08
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-RPT — Reports

Cross-cutting rules apply to all reports: branch/date-range filters, permission-gated cost/profit columns, Excel/PDF export, and totals that reconcile with source documents. Reports over ~2 s or ~10k rows are generated asynchronously (A-027).

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-RPT-001 | Sales summary / day book (branch, date, user) with payment-split totals | Acct | M | Matches invoices for the period |
| FR-RPT-002 | Sales by item (qty, revenue, discount, VAT, margin where permitted) | BM | M | Reconciles with sales register |
| FR-RPT-003 | Sales by category / manufacturer / generic | BM | M | Drill-down to items |
| FR-RPT-004 | Sales by customer with due view | SO/BM | M | Reconciles with customer ledgers |
| FR-RPT-005 | Sales by sales representative | BM | M | Uses invoice attribution |
| FR-RPT-006 | Sales by doctor (promoted-medicine attribution) | BM | M | Uses line/invoice doctor references |
| FR-RPT-007 | Sales by territory (roll-up hierarchy) | BM | M | Follows FR-TER-003 |
| FR-RPT-008 | Purchase register / summary by period, supplier, branch | Acct | M | Matches purchases |
| FR-RPT-009 | Purchases by item / category / supplier | WM | M | Includes bonus quantities shown separately |
| FR-RPT-010 | Stock on hand summary (medicine × branch, aggregate) | WM | M | Reconciles with batch stock |
| FR-RPT-011 | Stock valuation at batch cost (branch/company) | Acct | M | Equals Σ batch qty × batch cost |
| FR-RPT-012 | Batch expiry report: near-expiry and expired with days-to-expiry, qty, value | WM/BM | M | Threshold filter (30/60/90/180 days) |
| FR-RPT-013 | Low-stock / reorder report vs reorder levels | WM | M | At/below reorder flagged |
| FR-RPT-014 | Stock movement report (ledger) per medicine/batch/period/type | WM | M | Reconciles with ledger |
| FR-RPT-015 | Slow-moving and dead-stock report | BM | S | Configurable windows |
| FR-RPT-016 | Damage / write-off / adjustment report | BM | M | Groups by reason |
| FR-RPT-017 | Customer ledger report (per customer, date range) | Acct | M | Matches ledger exactly |
| FR-RPT-018 | Customer due / AR aging report | Acct | M | Buckets per FR-FIN-011 |
| FR-RPT-019 | Collection report (by collector, method, branch, day) | Acct | M | Matches payments |
| FR-RPT-020 | Supplier ledger report | Acct | M | Matches ledger exactly |
| FR-RPT-021 | Supplier payable / AP aging report | Acct | M | Buckets per FR-FIN-012 |
| FR-RPT-022 | Purchase return (debit note) report | Acct | M | Groups by supplier/reason |
| FR-RPT-023 | Sales return (credit note) report | Acct | M | Groups by customer/reason |
| FR-RPT-024 | Exception report: below-cost sales, credit overrides, FEFO overrides, no-invoice returns, free goods, duplicate-invoice overrides | Owner | M | Each exception links to its document |
| FR-RPT-025 | Expense report by category/period/branch | Acct | M | Matches expense entries |
| FR-RPT-026 | Other income report | Acct | M | Matches income entries |
| FR-RPT-027 | Profit report: gross and net, by period/branch/item/category; comparison columns | Owner | M | Reconciles with FR-FIN-013/014 |
| FR-RPT-028 | VAT summary report (output, input, net) with rate breakup | Acct | M | Feeds filing preparation |
| FR-RPT-029 | Doctor visit / coverage report | BM | M | Planned vs actual, samples |
| FR-RPT-030 | Representative performance report (sales, collection, visits) | BM | M | Target vs achievement where targets exist |

## FR-DASH — Dashboard

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-DASH-001 | Role-based landing dashboard (Owner/BM operational, SO sales-focused, MR field-focused; fallback default) | All | M | Wrong-role widgets never leak restricted data |
| FR-DASH-002 | KPI cards: today's sales, collection, dues, purchases, payables, cash position, stock value, profit MTD (permission-gated) | Owner/BM | M | Values match reports for same date |
| FR-DASH-003 | Charts: sales trend (30 days), top items/categories/customers | BM | M | Period selector applies |
| FR-DASH-004 | Alerts panel: near-expiry, expired, low stock, overdue dues, pending approvals | All | M | Each alert links to the filtered list |
| FR-DASH-005 | Branch comparison table for multi-branch roles | Owner | M | Scoped to permitted branches |
| FR-DASH-006 | Quick actions: new sale, collect payment, new purchase, expense, log visit | All | M | Actions respect permissions |
| FR-DASH-007 | Global date-range selector and manual refresh; cached ≤ 60 s | All | S | Refresh consistent across widgets |
| FR-DASH-008 | Dedicated mobile dashboard layout (cards, no wide tables) | All | M | Usable at 360 px width |

## FR-SRCH — Search & Filters

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-SRCH-001 | Global search across medicines, customers, suppliers, invoices, purchases, doctors, with permission-aware results | All | M | Unauthorized entities never appear (not even counts) |
| FR-SRCH-002 | Typeahead with keyboard navigation and recent items | All | M | p95 < 300 ms |
| FR-SRCH-003 | Barcode lookup endpoint for future scanning; returns medicine and batches | All | S | Exact-match fast path |
| FR-SRCH-004 | Recent searches per user (private) | All | S | Clearable |
| FR-SRCH-005 | Saved filter presets per user per list (e.g., "My today's dues") | All | S | Stored per user; no cross-user leakage |
| FR-SRCH-006 | All searches and filters respect branch scope and permissions | Sys | M | Security tests cover search endpoints |

## FR-NOTIF — Notifications

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-NOTIF-001 | In-app notification center: unread count, list, mark read/all, deep links | All | M | Delivered within 60 s of event |
| FR-NOTIF-002 | Low-stock alerts (event + daily digest) to WM/BM | Sys | M | Respects reorder levels |
| FR-NOTIF-003 | Near-expiry and expired-stock alerts (daily digest; configurable thresholds) | Sys | M | Matches expiry reports |
| FR-NOTIF-004 | Overdue invoice alerts to collector/accountant (internal) | Sys | M | Grouped per customer |
| FR-NOTIF-005 | Payment received notification to relevant roles | Sys | S | Deep link to receipt |
| FR-NOTIF-006 | Pending-approval notifications (expenses, adjustments, overrides) | Sys | M | Deep link to approval queue |
| FR-NOTIF-007 | Planned-visit reminders for MRs | Sys | S | Day-before reminder |
| FR-NOTIF-008 | Notification preferences per user per type (in-app always available for critical) | All | M | Critical alerts cannot be disabled |
| FR-NOTIF-009 | Email channel for configured notification types | Sys | S | Provider configured in settings |
| FR-NOTIF-010 | SMS channel adapter for external messages (due reminders, OTP); provider pluggable (Q-043) | Sys | S | Delivery attempts logged |
| FR-NOTIF-011 | Message template management for external channels (variables, preview) | Adm | S | Templates versioned |
| FR-NOTIF-012 | Notification log with delivery status (sent/failed/skipped) and retry | Sys | S | Failures visible to admins |

## FR-AUD — Audit Logs

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-AUD-001 | Capture every state-changing action: actor, branch, entity, entity id, action, before/after snapshot (JSON), IP, user agent, request id, timestamp | Sys | M | No business mutation occurs without an audit entry |
| FR-AUD-002 | Audit records are immutable from the application (no update/delete endpoints) | Sys | M | Tests confirm write-once behavior |
| FR-AUD-003 | Search/filter audit by entity type, entity id, actor, action, date range, branch | Adm | M | Results paginated |
| FR-AUD-004 | Document timeline view: all audit events for one document in one screen | All | M | Access limited to permitted roles |
| FR-AUD-005 | Login/authentication history per user | Adm | M | Includes failures and lockouts |
| FR-AUD-006 | Role/permission change history | Owner | M | Before/after visible |
| FR-AUD-007 | Export audit extracts (CSV) for compliance with filters | Owner | S | Export itself audited |
| FR-AUD-008 | Retention 7 years; archival of older partitions with restore procedure | Sys | M | Archived data retrievable within 4 h |
| FR-AUD-009 | Audit module access restricted to Owner/Super Admin (configurable read roles) | Sys | M | 403 for others |
| FR-AUD-010 | Failed authorization attempts (403/401) logged for security monitoring | Sys | M | Rate/anomaly visibility |

## FR-SET — Settings & Configuration

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-SET-001 | Company profile: name, logo, address, contacts, BIN/VAT, licenses | Owner | M | Appears on documents |
| FR-SET-002 | Fiscal year configuration (July–June) and period management (open/lock/reopen) | Owner | M | Locks enforced everywhere |
| FR-SET-003 | Currency and rounding settings (BDT, 2 dp; round-off toggle) | Owner | M | Applied consistently |
| FR-SET-004 | VAT settings: default rate, inclusive/exclusive mode, rate list | Owner | M | New medicines inherit default |
| FR-SET-005 | Document numbering series per branch: invoice, receipt, credit note, debit note, purchase, payment voucher, adjustment; prefix/suffix/width | Owner | M | Applied at allocation; changes never renumber history |
| FR-SET-006 | Approval thresholds: discount, credit override, expense, write-off/adjustment, transfer, backdate, period override | Owner | M | Enforced per role |
| FR-SET-007 | Credit policy defaults: credit days, limit behavior, overdue blocking rules | Owner | M | Defaults used when customer has none |
| FR-SET-008 | Expiry alert thresholds (company default + per-medicine override) | Owner | M | Feeds alerts/reports |
| FR-SET-009 | Reorder level defaults per medicine; bulk update tool | WM | M | Feeds low-stock alerts |
| FR-SET-010 | Price tier defaults and margin floor configuration | Owner | M | Feeds pricing and guards |
| FR-SET-011 | Payment methods and their financial account mappings | Acct | M | Payment entry uses mapping |
| FR-SET-012 | Notification settings: channels, provider credentials (encrypted at rest), sender identities | Owner | S | Credentials never exposed via API |
| FR-SET-013 | Document templates: invoice, receipt, credit/debit note, purchase voucher; logo, fields, copies, footer text | Owner | M | Template changes take effect for new prints |
| FR-SET-014 | Branch settings overrides with inheritance from company defaults | SA | M | Overrides clearly flagged |
| FR-SET-015 | Localization: timezone (Asia/Dhaka), date/number formats | SA | M | Applied UI/API-wide |
| FR-SET-016 | Feature flags: walk-in customer, auto-apply advance, Rx enforcement mode, free-goods schemes | Owner | M | Flags enforced server-side |
| FR-SET-017 | Password and session policy settings (length, expiry, lockout, idle timeout) | SA | M | Applied to auth flows |
| FR-SET-018 | System status page for admins: backup status, queue health, reconciliation results (read-only) | SA | S | Data from monitoring integrations |

---

*End of functional requirements. Non-functional requirements: `07-non-functional-requirements.md`. Business rules: `08-business-rules.md`.*
