# Go-Live Checklist

Cutover checklist for migrating from legacy records (Excel/paper) to the ERP. Do not skip the dry run.

## 1. Freeze & settings (T-7 days)

- [ ] Business data freeze agreed with all branches (no new manual ledgers after a cut-off timestamp)
- [ ] Invoice numbering series configured per branch (`INV-{BRANCH}-{YY}-…`) and tested
- [ ] Company profile, BIN/VAT numbers, fiscal year (July–June) confirmed in Settings
- [ ] Expense/income categories reviewed; approval thresholds set (expense, stock adjustment, transfer)
- [ ] Credit policy defaults set (limit behavior, overdue block days)
- [ ] Invoice/receipt document templates provided by the client and loaded
- [ ] Roles assigned to staff; branch access verified; owner account password changed

## 2. Data preparation (T-7 to T-1)

- [ ] Medicine list exported and cleaned (unique codes, correct units, VAT rates, reorder levels)
- [ ] Opening stock counted by batch with expiry dates — template `opening-stock.csv` filled
- [ ] Customer dues list aged and agreed — `opening-balances.csv` (CUSTOMER rows)
- [ ] Supplier payables agreed with suppliers — `opening-balances.csv` (SUPPLIER rows)
- [ ] Cash/bank/MFS balances reconciled — `opening-accounts.csv`
- [ ] User list with roles/branches prepared — `users.csv`

## 3. Staging dry run (T-3)

- [ ] All import commands run with `--dry-run`; error report empty
- [ ] Real import executed in staging; reconciliation pack produced:
  - opening stock value (per branch) equals physical valuation
  - total customer receivables equals agreed dues list
  - total supplier payables equals agreed payables list
  - total account balances equal cash/bank/MFS reconciliation
- [ ] Test transactions in staging: one purchase, one sale, one collection, one return
- [ ] `check_stock_integrity` and `check_ledger_integrity` both clean

## 4. Cutover day (T-0)

- [ ] Final legacy backup taken (Excel files archived, read-only)
- [ ] Database backup taken immediately before import (`backup_db`)
- [ ] Imports executed in order: **medicines → users → opening stock → opening balances → opening accounts**
- [ ] Reconciliation pack run and signed off by owner/accountant
- [ ] Users activated; legacy sheet locked; training reminders sent

## 5. Post go-live (T+1 to T+14, hypercare)

- [ ] First real purchase receipt checked against supplier bill
- [ ] First real sale: invoice total, FEFO batch, stock and due verified
- [ ] First collection: receipt, allocation and aging verified
- [ ] Daily: run integrity checks; review exception report (overrides, below-cost)
- [ ] Week 1 review: dues aging, stock counts spot-check, user feedback triaged

## 6. Rollback triggers

Return to legacy records only if: opening balances cannot be reconciled after fixes, or critical business flows are blocked > 1 business day with no workaround. Rollback steps: stop new entries, export ERP transactions since go-live, resume legacy books, re-import later with merged data.
