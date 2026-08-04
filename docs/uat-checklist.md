# UAT Checklist — Medicine Dealer ERP (Sprint 17)

Runnable user-acceptance script. Each scenario lists the steps and the expected
result. Mark PASS/FAIL and add sign-off. Covers the SRS §16.1 critical
scenarios plus the core V1 workflows.

## Preparation

- [ ] Test environment: backend on `:8000`, frontend on `:3000` (or staged build).
- [ ] Login as `01700000000 / Admin@1234` (owner).
- [ ] Confirm a second user exists for each role under test (Sales Operator
      `01700000007`, Accountant, Warehouse Manager).
- [ ] Opening data imported and reconciled (see `docs/operations.md` imports).

## A. Inventory & batches

| # | Scenario | Steps | Expected |
|---|---|---|---|
| A1 | Batch creation | Items → Add batch with expiry + qty | Batch appears in list with status ACTIVE |
| A2 | Expired batch cannot be sold | Sale entry → pick medicine → override batch to an expired batch | Backend rejects with `BATCH_EXPIRED` (409) |
| A3 | FEFO proposal | Sale entry → medicine with multiple batches | FEFO preview lists earliest-expiry first |
| A4 | Oversell race | Two operators confirm the same last stock simultaneously | One succeeds, the other gets `INSUFFICIENT_STOCK` |
| A5 | Low stock alert | Set a medicine's reorder level above on-hand | Daily stock job (or `/notifications`) shows LOW_STOCK |

## B. Purchasing

| # | Scenario | Steps | Expected |
|---|---|---|---|
| B1 | Purchase to stock | Register purchase with 2 lines incl. bonus + batch, confirm | Stock increases incl. bonus; supplier ledger +; purchase number assigned |
| B2 | Atomicity | Confirm purchase with an invalid line (qty > available in 2nd run) | Nothing partially posted (stock/ledger unchanged) |
| B3 | Purchase print | Purchases → click purchase number | Detail page renders; Print (A4) works |
| B4 | Purchase return | Return a line, confirm | Stock restored/removed per disposition; supplier ledger adjusted |
| B5 | Supplier statement | Suppliers → Statement CSV | CSV with running balance downloads |

## C. Sales, invoices & dues

| # | Scenario | Steps | Expected |
|---|---|---|---|
| C1 | Sale to invoice | New invoice → add lines → FEFO proposed → pay partial via account → confirm | Stock decreases; customer ledger +; invoice number; paid/partial badges |
| C2 | Credit limit | Customer at credit limit → new sale above limit | Blocked `CREDIT_LIMIT_EXCEEDED` unless override (permission) |
| C3 | Credit hold | Hold a customer in Customer edit → attempt sale | Blocked with hold reason |
| C4 | Invoice print | Sales → invoice number → Print (A4) | A4 layout, badges hidden, total correct |
| C5 | Collection | Dues → customer → enter collection, allocate to oldest invoice | Invoice paid_total +; customer balance −; receipt number |
| C6 | Payment reversal | Payments → receipt → Reverse with reason | Invoice due restored; account balance restored; history kept |
| C7 | Sale return | Return a line (resellable) → confirm | Stock restored to sellable pool; customer balance reversed |
| C8 | Customer statement | Customers → Statement CSV | CSV with running balance |

## D. Adjustments & expiry

| # | Scenario | Steps | Expected |
|---|---|---|---|
| D1 | Below-threshold adjustment | Adjustment ≤ threshold (default 5000) | Posts immediately |
| D2 | Above-threshold approval | Adjustment > threshold | PENDING_APPROVAL; requester cannot approve own; approver posts |
| D3 | Damage/expiry disposal | Expired batch → adjustment DECREASE with disposition | Loss value appears in P&L losses |

## E. Finance

| # | Scenario | Steps | Expected |
|---|---|---|---|
| E1 | Expense posting | Expense with receipt attachment, pay from account | Account balance −; expense register entry; P&L expenses + |
| E2 | Income posting | Other income to account | Account balance +; P&L other income + |
| E3 | Reversals | Reverse an expense and an income with reason | Account restored; status REVERSED; audit row |
| E4 | Profit report | Reports → Profit & Loss | Net revenue − COGS − expenses + income = net profit; CSV downloads |
| E5 | Financial position | Reports → Financial position | Receivables/payables/cash/stock shown; CSV downloads |

## F. Cheques

| # | Scenario | Steps | Expected |
|---|---|---|---|
| F1 | Received cheque lifecycle | Cheques → register received → deposit → clear | Statuses transition; invalid transitions blocked (400) |
| F2 | Issued cheque | Register issued → mark paid | Status PAID; stop after paid blocked |
| F3 | Bounce | Deposit then bounce | Status BOUNCED |

## G. Platform & controls

| # | Scenario | Steps | Expected |
|---|---|---|---|
| G1 | Fiscal lock | Settings → Fiscal periods → lock current month (reason) | Posting in locked month blocked `PERIOD_LOCKED`; owner override works; unlock restores |
| G2 | Idempotent double-click | Confirm a sale and immediately repeat the request (same key) | Only one invoice created; second returns the same |
| G3 | Audit trail | Perform sale confirm, cancel, expense, period lock | Audit page shows each with actor, IP, before/after |
| G4 | Roles | Login as Sales Operator → attempt expense posting / adjustment approve | Permission denied (403) |
| G5 | Global search | Search a medicine barcode, customer name, invoice number | Grouped results with deep links |
| G6 | Branch switch | Switch branch in topbar | Lists and posting default to new branch |
| G7 | Notifications | Bell → unread list → open deep link | Count decrements; deep link navigates |
| G8 | Attachments | Expenses → Files → upload PDF/CSV; download | 10 MB + type whitelist enforced; download round-trip |
| G9 | Barcode line add | Sales → scan input → barcode + Enter | New line added with the medicine; availability hint shown |
| G10 | Keyboard entry | Sales → Enter on last line | New line added; focus flows |

## H. Data integrity (post-session)

- [ ] `python manage.py check_stock_integrity` → OK
- [ ] `python manage.py check_ledger_integrity` → OK
- [ ] Backup taken (`manage.py backup_db`)

## Sign-off

| Role | Name | Date | Verdict |
|---|---|---|---|
| Owner | | | |
| Accounts | | | |
| Sales | | | |
| Stock | | | |

Deviation notes: automated unit tests remain deferred (project decision);
verification is via the `/tmp/smoke_s*.py` scripts plus this checklist.