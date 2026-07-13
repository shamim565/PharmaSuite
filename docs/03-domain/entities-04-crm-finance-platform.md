# Entity Catalog 4 — CRM, Finance & Platform

**Document ID:** DOC-ENT-04
**Parent:** `docs/03-domain-model.md`
**Conventions:** see `entities-01`. Ledgers append-only; platform tables audited.

---

## CRM

### DB-CRM-001 Doctor
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(20) | ✔ | Unique among non-deleted |
| `name` | txt(150) | ✔ | Trigram search |
| `gender` | enum | ○ | |
| `phones` | jsonb | ✔ | ≥ 1 phone; multiple allowed |
| `email` | txt(254) | ○ | |
| `specialty` | txt(120) | ○ | Indexed |
| `degrees` | txt(200) | ○ | |
| `doctor_type` | enum | ✔ | CONSULTANT / GP / OTHER |
| `registration_no` | txt(50) | ○ | BMDC/registration; unique when present |
| `category` | enum | ✔ | A / B / C (segment, FR-DOC-004) |
| `potential_rating` | enum | ○ | HIGH / MEDIUM / LOW |
| `territory_id` | fk→Territory | ○ | |
| `visit_frequency_target` | int | ○ | Per month (FR-DOC-019) |
| `status` | enum | ✔ | ACTIVE / INACTIVE |
| `consent_note` | txt | ○ | Privacy note (FR-DOC-018) |
| `notes` | txt | ○ | Append-only note entries audited |
**Relationships:** 1:N DoctorChamber, DoctorMedicine, DoctorVisit; M:N Representative via RepresentativeAssignment; M:N Medicine via DoctorMedicine; referenced by SalesInvoice/Items (attribution).
**Soft delete:** deactivate; merge blocked when both have visits/sales.

### DB-CRM-002 DoctorChamber
`doctor_id`, `name`, `address`, `visiting_hours` jsonb, `phone`; 1:N per doctor; soft delete.

### DB-CRM-003 DoctorMedicine
| Field | Type | Req | Rules |
|---|---|---|---|
| `doctor_id`, `medicine_id` | fk | ✔ | |
| `priority` | enum | ○ | HIGH / MEDIUM / LOW |
| `strength_note` | txt | ○ | |
| `effective_from` | date | ✔ | |
| `effective_to` | date | ○ | Historical mappings retained (BR-CRM-005) |
| `created_by` | fk→User | ✔ | |
**Constraint:** partial unique `(doctor_id, medicine_id) WHERE effective_to IS NULL` (one active mapping per pair).

### DB-CRM-004 DoctorVisit
| Field | Type | Req | Rules |
|---|---|---|---|
| `doctor_id`, `mr_rep_id` | fk | ✔ | One MR and one doctor (BR-CRM-002) |
| `branch_id` | fk | ✔ | Branch-scoped |
| `status` | enum | ✔ | PLANNED / COMPLETED / MISSED / CANCELLED (state machine §10) |
| `planned_date` | date | ○ | Present for planned visits |
| `visited_at` | ts | ○ | Present when completed |
| `purpose` | txt | ○ | |
| `products_discussed` | jsonb | ○ | Array of medicine ids (validated against mapping) |
| `outcome` | enum | ○ | INTERESTED / NEUTRAL / NOT_INTERESTED / PRESCRIBING |
| `next_visit_date` | date | ○ | |
| `notes` | txt | ○ | |
| `missed_reason` | txt | ○ | Required when MISSED |
| `edit_locked_at` | ts | ○ | Set 24 h after completion (configurable, FR-DVIS-009) |
**Indexes:** `(mr_rep_id, visited_at)`, `(doctor_id, visited_at)`, `(branch_id, status, planned_date)`.
**Audit:** all edits audited; after lock only BM/Admin edits.

### DB-CRM-005 DoctorVisitSample
`visit_id`, `medicine_id`, `batch_id`, `qty` (base units), `unit_cost` (batch cost), `inventory_transaction_id` (the PROMO_ISSUE movement); qty ≤ promo available (UC-DVIS-001 E1); links sample ↔ stock ↔ doctor for history and leakage control.

### DB-CRM-006 Representative
`code` unique, `name`, `rep_type` enum(SALES/MEDICAL), `phone`, `branch_id`, `user_id` (optional 1:1 link), `reports_to_id` self-FK, `joined_at`, `status` ACTIVE/INACTIVE; deactivation guard requires reassignment (FR-REP-015).

### DB-CRM-007 RepresentativeAssignment
| Field | Type | Req | Rules |
|---|---|---|---|
| `rep_id` | fk→Representative | ✔ | |
| `entity_type` | enum | ✔ | CUSTOMER / DOCTOR / TERRITORY |
| `entity_id` | uuid | ✔ | Polymorphic reference (value + index) |
| `effective_from` | date | ✔ | |
| `effective_to` | date | ○ | Null = current |
| `is_primary` | bool | ✔ | One primary per customer pair in MVP |
**Constraint:** partial unique `(rep_id, entity_type, entity_id) WHERE effective_to IS NULL`.
**History:** never deleted; reassignments close previous rows.

### DB-CRM-008 Territory
`name`, `parent_id` self-FK, `type` enum(REGION/AREA/TERRITORY), `status`; unique `(parent_id, name)`; acyclic enforced; deactivation blocked with active assignments.

### DB-CRM-009 RepresentativeTarget
`rep_id`, `period_year`, `period_month`, `target_sales_value` num(14,2), `target_sales_qty` num(14,3), `target_visit_count` int, `created_by`; unique `(rep_id, period_year, period_month)`; edits audited while period open.

---

## Finance

### DB-FIN-001 FinancialAccount
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(20) | ✔ | Unique |
| `name` | txt(120) | ✔ | |
| `account_type` | enum | ✔ | CASH / BANK / MFS |
| `branch_id` | fk→Branch | ○ | Null = company-level; branch accounts scoped |
| `provider`, `account_number` | txt | ○ | Masked without payment permission |
| `allow_negative` | bool | ✔ | Default false (BR-FIN-008) |
| `balance_cache` | num(14,2) | ✔ | Derived + reconciled |
| `status` | enum | ✔ | ACTIVE / INACTIVE |

### DB-FIN-002 FinancialTransaction *(append-only)*
`account_id`, `entry_type` (OPENING, SALE_RECEIPT, PURCHASE_PAYMENT, EXPENSE, INCOME, TRANSFER_IN/OUT, DEPOSIT, WITHDRAWAL, REFUND, ADVANCE_REFUND, CHEQUE_REVERSAL), `amount_delta` num(14,2), `transfer_group_id` uuid ○, `reference`, `source_type/id/number`, `transaction_group_id`, `reverses_entry_id`, `idempotency_key`, `business_date`, `seq`.
**Indexes:** `(account_id, seq)`, `(account_id, business_date)`, `(transfer_group_id)`, `(source_type, source_id)`.

### DB-FIN-003 Expense
`number`, `branch_id`, `business_date`, `category_id`, `amount` num(14,2) > 0, `account_id`, `payee`, `reference`, `attachment_id`, `status` PENDING/POSTED/REJECTED/REVERSED, `requested_by`, `approved_by`, `approved_at`, `posted_at`, `reversal_of_id`, `note`, `idempotency_key`.
**Rules:** threshold routes to approval; dual control; posting creates account transaction; reversal compensating only.

### DB-FIN-004 ExpenseCategory
`name` unique, `is_system` bool, `status`; seeded defaults (rent, utilities, transport, packaging, marketing, doctor samples, repairs, miscellaneous); deactivate-only when used.

### DB-FIN-005 Income
Mirror of Expense: `number`, `branch_id`, `business_date`, `category_id`, `amount`, `account_id`, `source/payer`, `reference`, `attachment_id`, `status` POSTED/REVERSED, `requested_by`, `reversal_of_id`, `note`, `idempotency_key`.

### DB-FIN-006 IncomeCategory
`name` unique, `is_system` bool, `status`; seeded (commission, service income, scrap sales, rent income, miscellaneous).

### DB-FIN-007 FiscalPeriod
`fiscal_year` int (e.g., 2026 = FY2026-27), `period_month` int 1–12, `start_date`, `end_date`, `status` OPEN/LOCKED, `locked_by`, `locked_at`, `reopen_reason`, `reopened_by`, `reopened_at`; unique `(fiscal_year, period_month)`.
**Rules:** postings checked against `business_date`; LOCKED blocks unless Owner override (BR-DOC-004, BR-FIN-007).

---

## Platform

### DB-SYS-001 AuditLog *(append-only, immutable)*
| Field | Type | Req | Rules |
|---|---|---|---|
| `actor_id` | fk→User | ○ | Null for system actions with `actor_type=SYSTEM` |
| `actor_type` | enum | ✔ | USER / SYSTEM |
| `branch_id` | fk→Branch | ○ | |
| `entity_type`, `entity_id` | txt/uuid | ✔ | Indexed pair |
| `action` | txt(50) | ✔ | create/update/confirm/cancel/reverse/approve/login/override/… |
| `before`, `after` | jsonb | ○ | Redacted snapshots (no secrets/PII beyond allowed fields) |
| `request_id`, `ip`, `user_agent` | txt | ○/✔ | Correlation |
| `created_at`, `seq` | ts/bigint | ✔ | UTC + identity |
**Indexes:** `(entity_type, entity_id, seq)`, `(actor_id, created_at)`, `(action, created_at)`, `(request_id)`.
**Rules:** no UPDATE/DELETE (trigger); retention 7 years; partition-ready (NFR-AUD-002).

### DB-SYS-002 Notification
`user_id`, `type` (LOW_STOCK, NEAR_EXPIRY, EXPIRED, OVERDUE, APPROVAL, VISIT_REMINDER, REPORT_READY, PAYMENT_RECEIVED), `severity` INFO/WARNING/CRITICAL, `title`, `body`, `deep_link`, `payload` jsonb, `is_read`, `read_at`, `created_at`; index `(user_id, is_read, created_at)`; critical types cannot be muted (FR-NOTIF-008).

### DB-SYS-003 NotificationTemplate
`code` unique, `channel` enum(IN_APP/EMAIL/SMS), `subject`, `body_template`, `variables` jsonb, `status`, `version`; changes audited; used by notification service.

### DB-SYS-004 Setting
`key` txt(100), `branch_id` nullable (null = company scope), `value` jsonb, `updated_by/at`; unique `(key, branch_id)` (company scope via partial unique on null); reads resolve branch → company inheritance (FR-BRANCH-008); secrets (provider credentials) stored encrypted via app envelope encryption, never returned by API.

### DB-SYS-005 IdempotencyKey
`actor_id`, `endpoint`, `key` txt(120), `request_hash`, `response_status` int, `response_body` jsonb, `created_at`, `expires_at` (default 24 h); unique `(actor_id, endpoint, key)`; replay returns stored response (BR-AUD-004); cleaned by daily job.

### DB-SYS-006 Attachment
`owner_type`, `owner_id`, `file_name`, `content_type`, `size_bytes`, `storage_key`, `checksum`, `uploaded_by`, `created_at`; index `(owner_type, owner_id)`; validated type/size (NFR-SEC-005); accessed via time-limited URLs.

### DB-SYS-007 ReportJob
`report_code`, `params` jsonb, `requested_by`, `status` QUEUED/RUNNING/DONE/FAILED, `file_key`, `error`, `created_at`, `started_at`, `finished_at`, `expires_at`; async report delivery (UC-RPT-003, A-027).

---

## Entity ↔ Use Case Map (this file)

| Entity group | Primary UCs |
|---|---|
| Doctor, DoctorChamber, DoctorMedicine | UC-DOC-001…003, UC-DVIS-001 |
| DoctorVisit, DoctorVisitSample | UC-DVIS-001…003 |
| Representative, RepresentativeAssignment, Territory, RepresentativeTarget | UC-REP-001…003, UC-TER-001, UC-DVIS-002 |
| FinancialAccount, FinancialTransaction | UC-FIN-003/005, UC-PAY-001, UC-PPAY-001 |
| Expense(+Category), Income(+Category) | UC-EXP-001…003, UC-INC-001/002 |
| FiscalPeriod | UC-FIN-002/007 |
| AuditLog | UC-AUD-001/002 (all writes) |
| Notification, NotificationTemplate | UC-NOTIF-001/002, UC-RPT-003 |
| Setting | UC-SET-001…004 |
| IdempotencyKey | All confirm/post endpoints (UC-SALE-002, UC-PAY-001, …) |
| Attachment | UC-PUR-001, UC-EXP-001, UC-DVIS-001 |
| ReportJob | UC-RPT-001/003 |
