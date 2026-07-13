# Open Questions — Client Confirmation Questionnaire

**Project:** Medicine Dealer ERP
**Document ID:** DOC-QST-001
**Status:** Open — awaiting client answers
**Last updated:** Phase 1 (Requirements Analysis)
**Response owner:** Business Owner / Client Sponsor
**How to answer:** fill the **Client answer** column and return. Until answered, the documented **Recommended default** is implemented, exactly as stated. Each answered question becomes a locked decision in `docs/assumptions-log.md`.

> **Rule:** no answer is "maybe". If the client is unsure, we keep the recommended default and record it as an assumption (A-###).

---

## 1. Pricing, Discounts & Credit

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-001 | May a user sell a medicine **below its batch cost**? | Yes, only with the `SALE_BELOW_COST` permission, with a reason code; every occurrence appears in a "Below-cost sales" report | Hard block loses flexibility on damaged/expiring stock; unconditional allowance hides margin leakage | | Open |
| Q-002 | What happens when a customer's **credit limit** is exceeded? | Hard block at confirmation; Owner/Admin with `SALE_OVERRIDE_CREDIT` + reason can override; override is audited and reported | Warning-only risks uncollectable dues; hard-block-only creates workflow friction for trusted customers | | Open |
| Q-003 | Are new credit sales blocked when a customer is **past credit days** with overdue invoices? | Warn by default; block only when overdue amount exceeds a configurable threshold (default: any invoice > 30 days overdue) | Aggressive blocking hurts trusted relationships; no blocking raises bad-debt exposure | | Open |
| Q-004 | Can sales/purchases/expenses be **backdated**? | Yes, backdating allowed within the current fiscal month only, with `DOC_BACKDATE` permission; period-locked months always blocked except Owner `PERIOD_OVERRIDE` | Unlimited backdating corrupts period reports; no backdating creates day-close friction | | Open |
| Q-005 | Can a **confirmed invoice be edited**? | No. Corrections are cancel + reissue (if unpaid/unreturned) or sales return/credit note. Drafts are freely editable | Editable confirmed invoices destroy ledger trust and auditability | | Open |
| Q-006 | Is pricing beyond the three tiers (Retail/Wholesale/Custom) needed — e.g., per-customer price lists or quantity breaks? | No in MVP (three tiers + line-level negotiated discount). Price lists are Phase 2 | Adds a pricing engine (~2–3 weeks) to MVP | | Open |
| Q-007 | Who may approve discounts, and up to what limit? | Cashiers: up to 5% line discount; Branch Manager: 10%; Admin/Owner: unrestricted. All discounts above 5% audited. Configurable thresholds | Rigid limits slow sales; loose limits enable margin abuse | | Open |

## 2. Inventory, Batches & Expiry

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-008 | Is **FEFO (First-Expiry-First-Out)** mandatory for batch selection? | Yes. System preselects FEFO batches; manual override requires `INV_OVERRIDE_FEFO` + reason | Optional FEFO increases expiry write-offs, the problem the ERP is meant to solve | | Open |
| Q-009 | Is an **expiry date mandatory** for every medicine? | Yes for all medicine items. Exempt only for items explicitly flagged `no_batch` (e.g., consumables) | Nullable expiry makes FEFO and expiry alerts unreliable | | Open |
| Q-010 | How should **near-expiry** stock behave — warn or block sale? | Warn when ≤ 90 days to expiry (configurable per medicine); block sale when ≤ 30 days or expired unless `INV_SELL_NEAR_EXPIRY` override | Early hard blocking strands saleable stock; no warning causes silent expiry losses | | Open |
| Q-011 | Should **draft invoices reserve stock**? | No. Availability is checked again atomically at confirmation; error shows exact shortages | Reservations prevent late-confirmation failures but add reservation expiry/holds and complexity | | Open |
| Q-012 | Are **multiple warehouses/store rooms per branch** required at launch? | No — one store per branch in MVP | Adds warehouse entity across inventory, purchases, sales, transfers | | Open |
| Q-013 | Is **negative stock ever permitted** (e.g., emergency sale before goods receipt)? | Never. Confirmation fails with `INSUFFICIENT_STOCK`; use urgent purchase/adjustment first | Allowing negative stock breaks batch costing and audit integrity | | Open |
| Q-014 | Do you need **walk-in cash customers** without an account? | Disabled by default; can be enabled with a single "Walk-in" pseudo-customer. Credit/dues always require a real customer | Cash sales speed up checkout but lose customer history/dues linkage | | Open |
| Q-015 | Is a **batch-specific selling price** ever needed (same medicine priced differently by batch)? | No. Selling price is set at medicine + price-tier level; batch affects cost only | Per-batch price overrides complicate pricing, reports and returns | | Open |
| Q-016 | Is physical **stock counting / verification** required in the MVP? | Phase 2. MVP provides adjustment documents for corrections; counts are a heavier workflow (freeze, count sheets, variance approval) | Manual trust in system stock until Phase 2 | | Open |

## 3. Documents, Tax & Fiscal

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-017 | What exact **invoice numbering format** do you use/want? | `INV-{BRANCH}-{YY}-{000001}`, gapless per branch per fiscal year; receipt `RCP-...`; credit note `CRN-...`; debit note `DBN-...` | Must match any format required by your VAT records | | Open |
| Q-018 | Provide the current **invoice/letterhead layout** (fields, copies, signatures). Is a VAT invoice (Mushak) layout required for printing? | VAT-compliant invoice fields included; exact statutory layout configured as a template once samples are provided | Printing/template work blocked until samples arrive | | Open |
| Q-019 | Is VAT applied at a **single 15% rate**, or do rates vary by product (e.g., 5%/15%/exempt)? | Rate stored per medicine (default 15%, options 0/5/10/15 configurable); VAT computed on discounted net line value | Product-level rate flexibility costs nothing extra; single-rate decision simply locks the defaults | | Open |
| Q-020 | Are prices entered **excluding VAT** (VAT added) or **including VAT** (VAT extracted)? | Exclusive by default, company-configurable per tenant setting | Pricing/computation and display logic switch | | Open |
| Q-021 | Confirm fiscal year **July–June** and monthly **period locking** after month close. Who may post into a locked period? | Confirmed. Lock after close; only Owner with `PERIOD_OVERRIDE`, always audited | Weak period control complicates VAT/management reporting | | Open |
| Q-022 | Confirm the **round-off convention**. | Round each line half-up to 2 decimals; a separate invoice round-off line adjusts the grand total to the nearest whole BDT (max ±0.50) | Cash reconciliation differences if a different convention is required | | Open |
| Q-023 | Should **delivery address, delivery date and delivered-by** be captured on invoices? | Yes (lightweight fulfillment tracking); no routing/fleet features | If omitted, delivery disputes cannot be traced | | Open |

## 4. Payments, Dues & Returns

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-024 | Are **advance customer payments** (payment before invoice) supported? | Yes — held as customer advance/on-account balance, applied manually or automatically at future confirmations | If not supported, prepayments must be parked in a suspense account outside the system | | Open |
| Q-025 | Is **automatic payment allocation** required? | Yes — FIFO by invoice date automatically; accountant may re-allocate manually with audit | Manual-only allocation slows collection desk and risks missed invoices | | Open |
| Q-026 | What should happen on **overpayment**? | Block overpayment on a single invoice beyond its outstanding; the excess can be explicitly recorded as advance | Simple block is safest; advance handling covers legitimate prepayment cases | | Open |
| Q-027 | Can a **sales return be accepted without the original invoice**? | No by default. `SRET_NO_INVOICE` permission can enable it; such returns are flagged in reports | Enabled returns weaken revenue audit; disabled returns may upset large customers | | Open |
| Q-028 | Default **refund method** for sales returns? | Credit to customer account (adjust against dues). Cash/bank refund requires `RETURN_REFUND` permission | Cash refunds drain the drawer and bypass due settlement | | Open |
| Q-029 | Are **cheque payments** common? Should the system track pending/cleared/bounced? | Yes — cheque lifecycle Pending → Cleared → Bounced; bouncing reverses allocations and re-opens invoices | Ignoring cheque states misstates collection and dues | | Open |
| Q-030 | Should **mobile financial services** (bKash/Nagad/Rocket) be separate account types? | Yes — generic "MFS wallet" financial account type with provider label | Bank-only accounts force MFS to be recorded as cash | | Open |

## 5. Accounting & Profit

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-031 | What **opening balance date** will you use at go-live? | First day of the go-live fiscal month (e.g., 1 Oct), entered as `OPENING` ledger entries | Mid-month cutover complicates reconciliation but is possible | | Open |
| Q-032 | Confirm **no formal double-entry GL in MVP** (subledgers + P&L only). Is a trial balance / balance sheet required at launch? | Confirmed no GL. If a balance sheet is legally required, it must be produced outside the system until Phase 3 | GL adds ~4–6 weeks and a dedicated accountant workflow | | Open |
| Q-033 | May a **cash account go negative** (temporary petty-cash overrun)? | No by default; per-account `allow_negative` setting can enable it with alert | Prevents accounting errors; may require discipline at the drawer | | Open |
| Q-034 | Which roles may see **cost and profit** figures? | Owner, Admin, Accountant: full. Branch Manager: branch-level. Others: hidden (server-enforced) | Wider visibility risks leaking supplier margins to staff | | Open |
| Q-035 | Are **expense approval thresholds** required? | Expenses above 5,000 BDT require Branch Manager/Admin approval; below posts immediately; configurable | No approvals risks uncontrolled spend; approvals add workflow | | Open |
| Q-036 | How should **supplier payments** be applied — invoice-wise (bill-wise) or against overall balance? | Bill-wise with FIFO default and manual allocation, exactly like customer payments | Balance-only payments lose invoice-level aging | | Open |

## 6. Doctors, Representatives & Promotion

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-037 | Is **doctor visit tracking** in the MVP? How detailed? | Yes, lightweight: plan, log visit (doctor, MR, purpose, products, samples, outcome, next date), reports. No GPS/photo in MVP (Phase 2) | Full field-force tooling (GPS, routes, attendance) adds 2–3 weeks | | Open |
| Q-038 | How should **samples/free goods given to doctors** be handled? | Issued from promotional stock, deducted from inventory with a `PROMO_ISSUE` movement and expensed under "Doctor Samples"; distribution logged per doctor | Untracked samples cause stock shrinkage and tax issues | | Open |
| Q-039 | Are **representative commissions/incentives** calculated in this system? | Phase 2. MVP tracks sales value, collections, visits per representative | Commission engine adds payroll-style complexity to MVP | | Open |
| Q-040 | What **doctor master fields** are required (BMDC registration no., specialty, degrees, chambers, category A/B/C, potential)? Is registration verification needed? | Fields captured as data; no external verification integration | External verification is a separate integration project | | Open |
| Q-041 | Is **sales attribution to doctors** needed on invoices (which doctor influenced the sale)? | Yes — optional doctor reference per invoice/line; used for doctor-wise sales reports | Without it, promoted-medicine ROI cannot be measured | | Open |

## 7. Platform, Compliance & Migration

| ID | Question | Recommended default | Consequence if different | Client answer | Status |
|---|---|---|---|---|---|
| Q-042 | Is **Bangla UI** required at launch? | English UI at launch; i18n architecture ready; Bangla in Phase 2 | Bangla at launch adds ~1 week of translation/QA | | Open |
| Q-043 | Which **SMS/email providers** should due reminders and OTP use? | Pluggable adapter; provider chosen at deployment. In-app notifications work regardless | Hard-coded provider creates rework if you change vendors | | Open |
| Q-044 | Confirm **audit log retention of 7 years** and that users cannot delete audit records. | Confirmed 7 years, immutable from application, storage only grows | Shorter retention may violate VAT/audit expectations | | Open |
| Q-045 | Is **multi-company** (separate legal entities) needed within 24 months? | No. Single entity; branches only | Multi-company adds tenant/consolidation design now | | Open |
| Q-046 | What does the **existing data** live in (Excel files, previous software, paper registers)? Please list all sources and formats. | We will provide import templates (Phase 11); sources must be inventoried before Sprint 8 | Data migration risk/effort cannot be estimated without inventory | | Open |
| Q-047 | Are there **regulatory reports** (e.g., DGDA drug registers, narcotics registers, Mushak returns) that the system must produce? | Not automated in MVP; a controlled-medicine register report can be added if your license requires it | Statutory gap risk; legal review needed | | Open |
| Q-048 | What is the **go-live pilot scope** — all branches at once or one pilot branch first? | One pilot branch for 2–4 weeks, then remaining branches in waves | Big-bang go-live raises operational risk | | Open |

---

## 8. Answer Processing

1. Client returns the completed table.
2. Answers are logged in `docs/assumptions-log.md` as `DEC-###` entries (or as closed `Q-###`).
3. Any requirement affected by a changed answer is updated in the FR catalog with a changelog note.
4. If an answer changes a locked decision (DEC-001..010), the affected phase gate re-opens.

*Unanswered questions do not block progress: the recommended defaults are implemented and marked here.*
