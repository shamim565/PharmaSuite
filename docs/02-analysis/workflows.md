# Workflow Diagrams (Textual)

**Document ID:** DOC-WF-001
**Parent:** `docs/02-system-analysis.md`
**Legend:** `[SO]` Sales Operator · `[WM]` Warehouse · `[AC]` Accountant · `[BM]` Branch Manager · `[MR]` Medical Rep · `[SYS]` System/Celery · `[CUS]` Customer · `[SUP]` Supplier. `⛁` DB transaction boundary. `✉` notification/print.

---

## 1. Purchase Workflow

```
[WM] Select supplier ─▶ create purchase draft
        │  header: supplier, invoice no/date, branch
        │  lines: medicine, batch no, expiry, qty(+bonus), cost, disc, VAT
        │  totals: effective cost (bonus allocated), VAT, round-off
        ▼
   Save draft (no stock effect, editable)
        │
        ▼
[WM] Confirm ──⛁ TRANSACTION────────────────────────────────────────────┐
        │ 1. validate lines + period open + duplicate invoice check     │
        │ 2. allocate number PUR-{BRANCH}-{YY}-{NNNNNN}                 │
        │ 3. batch create/merge (branch+medicine+batch+expiry)          │
        │ 4. stock ledger IN (purchase qty + bonus qty) @ effective cost│
        │ 5. supplier ledger: payable += grand total                    │
        │ 6. if paid now: account transaction + payment allocation      │
        └──────────────────────────────────────────────────────────────┘
        │
        ▼
   [CONFIRMED] ─✉ voucher/label ─▶ stock available (FEFO)
        │
        ├─ later: [AC] supplier payment (full/partial) ─▶ payable ↓
        ├─ later: [WM] purchase return ─▶ batch qty ↓, payable ↓ / advance ↑
        └─ cancel allowed only if: no payments AND no returns AND stock untouched
```

---

## 2. Sale Workflow

```
[SO] Select customer ─▶ create invoice draft
        │
        ├─ add medicine (search/barcode-ready)
        │      └─ [SYS] FEFO proposes batches (earliest expiry)
        │      └─ qty + tier price + line discount + VAT
        ├─ optional doctor reference per line
        ├─ invoice discount + round-off
        └─ delivery info, sales rep
        ▼
   Draft (no stock effect; no number)
        │
        ▼
[SO] Confirm ── checks ──────────────────────────────┐
        │ credit limit / overdue? ─ no ─▶ proceed      │
        │                          └ yes ─▶ [BM] override (perm+reason) or block
        │ below cost / margin floor? ─ yes ─▶ override (perm+reason) or block
        │ Rx required? ─ policy warn/require
        ▼
   ⛁ TRANSACTION───────────────────────────────────────────────────────┐
        │ 1. lock batch rows (deterministic order) + revalidate stock   │
        │ 2. deduct stock (base units), post stock ledger OUT           │
        │ 3. allocate invoice number INV-{BRANCH}-{YY}-{NNNNNN}         │
        │ 4. customer ledger: receivable += grand total                 │
        │ 5. paid-at-entry: payment + allocations + account transaction │
        │ 6. set states: lifecycle/payment/return/fulfillment           │
        └──────────────────────────────────────────────────────────────┘
        │
        ▼
   [CONFIRMED] ─✉ invoice PDF (print/share) ─▶ fulfillment pending
        │
        ├─ later: [AC] collection ─▶ payment status → PARTIALLY_PAID → PAID
        ├─ later: [SO/WM] sales return ─▶ stock back/quarantine, receivable ↓
        └─ cancel only if no payments & no returns (reversal; number kept VOID)
```

---

## 3. Due Collection Workflow

```
[SYS] Nightly aging refresh ─▶ due list (per customer/invoice/rep)
        │
[AC] Collection round ─▶ open due list ─▶ filter (overdue bucket, area, rep)
        │
        ├─ [SO/AC] collect at counter / field
        ▼
   Enter amount + method(s)+account(s)+reference+collector
        │
   [SYS] propose FIFO allocation (oldest invoice date first)
        │
        ├─ manual re-allocation (permitted roles)
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. lock invoice rows; validate Σ alloc ≤ amount,    │
        │    per-invoice ≤ outstanding                        │
        │ 2. post payment + allocations                       │
        │ 3. account transaction(s) per method                │
        │ 4. invoice payment states recompute                 │
        │ 5. excess → customer advance (explicit)             │
        └─────────────────────────────────────────────────────┘
        │
        ▼
   ✉ receipt (print/share) ─▶ due list & aging ↓
        │
[AC] cheque? ─▶ PENDING ─▶ CLEARED (stand) │ BOUNCED ─▶ reversal (UC-PAY-003)
```

---

## 4. Sales Return Workflow

```
[CUS] Return request with invoice ─▶ [SO] open original invoice
        │
   Select lines + quantities (≤ sold − already returned)
   Reason + per-line condition: RESELLABLE | DAMAGED | EXPIRED
        │
   [SYS] compute credit value (proportional discount + VAT reversal at original cost)
        │
        ├─ RESELLABLE & not expired ─▶ restock original batch
        └─ DAMAGED/EXPIRED ─▶ quarantine pool (non-saleable)
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. stock ledger IN (restock) or QUARANTINE movement │
        │ 2. customer ledger credit                           │
        │ 3. invoice return status recompute                  │
        │ 4. credit note number CRN-… allocated               │
        └─────────────────────────────────────────────────────┘
        │
        ▼
   [CONFIRMED] ✉ credit note
        │
[AC] refund method: customer credit (default) | cash | bank | adjust dues
        │  (cash/bank needs RETURN_REFUND permission + account transaction)
        ▼
   Exception report (if no-invoice return or override used)
```

---

## 5. Purchase Return Workflow

```
[WM] Defective/expired/wrong goods identified ─▶ open confirmed purchase
        │
   Select lines/batches + qty ≤ returnable (purchased − returned)
   Reason: damaged | expired | near-expiry agreement | wrong item | over-supply
        │
   [SYS] compute debit value incl. proportional VAT reversal
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. batch qty ↓ (goods leave stock)                  │
        │ 2. supplier ledger: payable ↓                       │
        │    if payable < 0 → supplier advance/receivable     │
        │ 3. debit note number DBN-… allocated                │
        └─────────────────────────────────────────────────────┘
        │
        ▼
   [CONFIRMED] ✉ debit note ─▶ [WM] pending pickup ─▶ [SUP] collects
        │
   Aging of pending pickups reported until collected
```

---

## 6. Stock Adjustment Workflow

```
Trigger: count variance | damage | expiry | found stock | data correction
        │
[WM] Create adjustment (branch, medicine, batch, direction, qty, reason, evidence)
        │
   [SYS] validate: qty ≤ available (decrease), period open, reason required
        │
        ├─ below approval threshold ─▶ post immediately
        └─ above threshold ─▶ PENDING_APPROVAL ─▶ [BM/Adm] review
                                                    ├─ approve ─▶ post
                                                    └─ reject (reason)
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. stock ledger entry (+/-) with source reference   │
        │ 2. cached balance update                            │
        │ 3. write-off/damage types → expense posting         │
        └─────────────────────────────────────────────────────┘
        │
   Reversal path: compensating adjustment (reason + permission, period rules)
   All events audited; adjustment register updated
```

---

## 7. Expense Workflow

```
[AC] Expense incurred
        │
   Enter: date, branch, category, amount, payment account, payee, reference, bill
        │
   [SYS] amount vs approval threshold?
        ├─ below ─▶ post now
        └─ above ─▶ PENDING_APPROVAL ─▶ [BM/Adm] approve ─▶ post | reject
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. account transaction (out)                        │
        │ 2. expense reflected in P&L / reports               │
        └─────────────────────────────────────────────────────┘
        │
   Reversal: compensating entry with reason (cross-period → Owner)
```

---

## 8. Income Workflow

```
[AC] Other income received (commission, service, scrap, rent)
        │
   Enter: date, branch, category, amount, account, payer/ref, note
        ▼
   ⛁ TRANSACTION─────────────────────────────────────────────┐
        │ 1. account transaction (in)                         │
        │ 2. income reflected in P&L                          │
        └─────────────────────────────────────────────────────┘
        │
   Voucher printable ─▶ reversal path via compensating entry (permission + reason)
```

---

## 9. Doctor Visit Workflow

```
[BM] Territory/doctor assignment ─▶ [MR] plan visits (week)
        │
   [SYS] day-before reminder notification
        │
[MR] On visit (mobile): select doctor (planned/ad-hoc)
        ├─ products discussed (doctor–medicine mapping)
        ├─ samples given: medicine, batch, qty
        │      └─ [SYS] PROMO stock check + deduction (non-saleable pool)
        ├─ outcome/interest, notes, next visit date
        ▼
   Save ─▶ visit recorded (editable within 24h, then BM/Adm only)
        │
   Missing plan? mark MISSED with reason
        ▼
[BM] Coverage report: planned vs actual, frequency per doctor, sample history
[BM] Doctor attributed sales report (invoice doctor references)
```

---

## 10. Month-End Reporting Workflow

```
[AC] Initiate close
   ┌─ Checklist run by [SYS] ─────────────────────────────────────┐
   │ • pending approvals (expenses/adjustments)                   │
   │ • reconciliation status: stock/customer/supplier/accounts    │
   │ • unallocated payments / advances review                     │
   │ • pending pickup purchase returns                            │
   │ • draft invoices/purchases not confirmed (report only)       │
   └──────────────────────────────────────────────────────────────┘
        │
   Generate close pack:
   • sales register + purchase register
   • VAT output/input/net with rate breakup
   • stock valuation + expiry summary
   • AR aging + AP aging
   • gross/net profit report
   • exception report (overrides, write-offs)
        ▼
[Owner] Review ─▶ resolve discrepancies ─▶ lock period (PERIOD_LOCK)
        │
   Postings into locked month blocked (override: Owner + reason + audit)
        ▼
   Archive pack to object storage ─▶ next month opens automatically
```

---

## Workflow ↔ Use Case ↔ Rule Map

| Workflow | Primary UCs | Key BRs |
|---|---|---|
| Purchase | UC-PUR-001/002/003/004, UC-BATCH-001 | BR-PUR-001…010, BR-BATCH-00x |
| Sale | UC-SALE-001…006 | BR-SALE-001…015, BR-INV-00x |
| Due collection | UC-PAY-001…006 | BR-PAY-001…009 |
| Sales return | UC-SRET-001…003 | BR-SRET-001…008 |
| Purchase return | UC-PRET-001/002 | BR-PUR-007/008/010 |
| Stock adjustment | UC-ADJ-001…003 | BR-INV-007/008, BR-BATCH-003 |
| Expense | UC-EXP-001…003 | BR-FIN-005, FR-EXP-003 |
| Income | UC-INC-001/002 | BR-FIN-005 |
| Doctor visit | UC-DVIS-001…003, UC-DOC-002 | BR-CRM-002/004 |
| Month-end | UC-FIN-002/007, UC-RPT-001/002 | BR-DOC-004, BR-FIN-003/007 |
