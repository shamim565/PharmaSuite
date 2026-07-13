# Entity Catalog 1 — Identity, Branch & Catalog

**Document ID:** DOC-ENT-01
**Parent:** `docs/03-domain-model.md`
**Conventions:** UUIDv7 PKs named `id`; common columns (`branch_id`, `created_at/by`, `updated_at/by`, `deleted_at`, `version`) omitted from tables except where noteworthy. Type shorthand: `txt`, `int`, `bool`, `date`, `ts` (timestamptz), `num(p,s)`, `enum`, `jsonb`, `fk→`.

---

## Identity & Access

### DB-IAM-001 User
**Purpose:** Staff identity and login principal.
| Field | Type | Req | Rules |
|---|---|---|---|
| `full_name` | txt(150) | ✔ | |
| `mobile` | txt(20) | ✔ | Unique among non-deleted; used as login identifier |
| `email` | txt(254) | ○ | Unique among non-deleted when present |
| `password_hash` | txt | ✔ | Argon2id; never exposed |
| `status` | enum | ✔ | PENDING_ACTIVATION / ACTIVE / DEACTIVATED / SOFT_DELETED (state machine §12) |
| `must_change_password` | bool | ✔ | Default false; true after admin reset/first login |
| `totp_secret` | txt (encrypted) | ○ | Present when 2FA enrolled |
| `totp_enabled` | bool | ✔ | |
| `recovery_codes_hash` | jsonb | ○ | Single-use recovery codes (hashed) |
| `default_branch_id` | fk→Branch | ○ | Required before first login |
| `locale` | txt(10) | ○ | Default `en` |
| `avatar_url` | txt | ○ | Object storage key |
| `failed_attempts` | int | ✔ | Reset on success; drives lockout |
| `locked_until` | ts | ○ | BR-AUTH-001 |
| `self_reset_disabled` | bool | ✔ | Blocks self-service reset |
| `last_login_at` | ts | ○ | |
**Relationships:** M:N Role via UserRole; M:N Branch via UserBranch; 1:N Session, LoginAttempt, PasswordHistory; referenced as `created_by/updated_by` everywhere (by value, no cascade).
**Constraints/indexes:** partial unique `(mobile)`, `(email)`; idx `(status)`; idx `(default_branch_id)`.
**Soft delete & audit:** soft delete only when history exists; last active Owner and self protected (FR-USER-009); all changes audited.

### DB-IAM-002 Role
**Purpose:** Named permission bundle with branch scope.
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(50) | ✔ | Unique; system roles immutable identities |
| `name` | txt(100) | ✔ | |
| `description` | txt | ○ | |
| `is_system` | bool | ✔ | System roles cannot be deleted |
| `branch_scope` | enum | ✔ | ALL / ASSIGNED |
**Relationships:** M:N Permission via RolePermission; M:N User via UserRole.
**Soft delete & audit:** clone-only for system roles; changes audited (BR-RBAC-013).

### DB-IAM-003 Permission
**Purpose:** Atomic capability (code-managed catalog).
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(80) | ✔ | Unique, stable, e.g., `SALE_OVERRIDE_CREDIT` |
| `module` | txt(30) | ✔ | Indexed |
| `action` | txt(30) | ✔ | view/create/edit/confirm/cancel/approve/export/override |
| `is_sensitive` | bool | ✔ | Sensitive permissions surfaced in audit reviews |

### DB-IAM-004 RolePermission
M:N join: `role_id`, `permission_id`, `effect` enum(ALLOW/DENY); unique `(role_id, permission_id)`; deny wins (BR-RBAC-002).

### DB-IAM-005 UserRole
M:N join: `user_id`, `role_id`, unique pair; assignment audited.

### DB-IAM-006 UserBranch
M:N join: `user_id`, `branch_id`, `is_default` bool; unique `(user_id, branch_id)`; at most one default per user (partial unique).

### DB-IAM-007 Session
| Field | Type | Req | Rules |
|---|---|---|---|
| `user_id` | fk→User | ✔ | |
| `refresh_token_hash` | txt | ✔ | Never store raw token |
| `family_id` | uuid | ✔ | Reuse detection revokes family (BR-AUTH-002) |
| `device_label`, `ip`, `user_agent` | txt | ○ | Device list UI |
| `expires_at` | ts | ✔ | Default 30 days |
| `revoked_at`, `reuse_detected` | ts/bool | ○ | |
**Indexes:** `(user_id)`, `(family_id)`, `(expires_at)`.

### DB-IAM-008 LoginAttempt
`identifier`, `user_id` (nullable), `ip`, `user_agent`, `success`, `failure_reason`, `created_at`; index `(identifier, created_at)`, `(ip, created_at)`; feeds lockout + audit.

### DB-IAM-009 PasswordHistory
`user_id`, `password_hash`, `created_at`; keep last N (config, default 5).

---

## Branch

### DB-BRN-001 Branch
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(20) | ✔ | Unique |
| `name` | txt(150) | ✔ | |
| `type` | enum | ✔ | HEAD_OFFICE / BRANCH |
| `address`, `phone`, `email` | txt | ○ | |
| `manager_user_id` | fk→User | ○ | |
| `bin`, `vat_reg`, `trade_license` | txt | ○ | Printed on documents |
| `invoice_prefix` | txt(10) | ✔ | Default from code |
| `opening_date` | date | ✔ | Start of operations |
| `status` | enum | ✔ | ACTIVE / INACTIVE |
| `settings_overrides` | jsonb | ○ | Branch settings inheritance (FR-BRANCH-008) |
**Constraints:** unique `(code)`; deactivation guard checks stock/balances/open items (FR-BRANCH-007).
**Audit:** all lifecycle events audited.

---

## Catalog

### DB-CAT-001 Medicine
**Purpose:** Sellable/purchasable item master.
| Field | Type | Req | Rules |
|---|---|---|---|
| `code` | txt(30) | ✔ | Unique among non-deleted |
| `brand_name` | txt(200) | ✔ | Indexed (trigram for search) |
| `generic_id` | fk→Generic | ✔ unless `no_batch` consumable | |
| `manufacturer_id` | fk→Manufacturer | ✔ | |
| `category_id` | fk→MedicineCategory | ✔ | |
| `dosage_form`, `strength`, `pack_description` | txt | ○/✔ | dosage_form required for medicines |
| `base_unit_id` | fk→Unit | ✔ | Stock unit |
| `trade_price`, `mrp` | num(14,2) | ○ | Reference prices |
| `retail_price`, `wholesale_price`, `custom_price` | num(14,2) | ○ | Tier prices (FR-CAT-003) |
| `last_purchase_cost` | num(14,4) | ○ | System-maintained, read-only to users |
| `vat_rate` | num(5,2) | ✔ | 0/5/10/15, default 15 |
| `shelf_life_months` | int | ○ | Defaults batch expiry suggestion |
| `near_expiry_days` | int | ○ | Overrides company default |
| `reorder_level` | num(14,3) | ○ | Per-medicine default; branch overrides via `StockBalance` config? (kept on medicine for MVP) |
| `preferred_supplier_id` | fk→Supplier | ○ | |
| `rx_required` | bool | ✔ | |
| `controlled_class` | txt(30) | ○ | e.g., schedule label |
| `cold_chain` | bool | ✔ | |
| `no_batch` | bool | ✔ | Exempt from expiry/FEFO (EC-042) |
| `status` | enum | ✔ | ACTIVE / INACTIVE / DISCONTINUED |
| `discontinued_at` | date | ○ | Blocks new purchases |
| `aliases` | jsonb | ○ | Search synonyms |
| `image_url` | txt | ○ | |
**Relationships:** N:1 Generic/Manufacturer/Category/Unit/Supplier; 1:N MedicineUnitConversion, MedicineBarcode, MedicineBatch; M:N Doctor via DoctorMedicine.
**Constraints/indexes:** unique partial `(code)`; idx `(brand_name)`, `(generic_id)`, `(manufacturer_id)`, `(category_id)`, `(status)`; trigram idx on brand/generic for search.
**Soft delete & audit:** referenced medicines deactivate; code/price changes audited with history view (FR-CAT-023).

### DB-CAT-002 Generic
`name` unique, `therapeutic_class`, `description`, `status`; delete blocked while referenced.

### DB-CAT-003 Manufacturer
`name` unique, `country`, `license_no`, `contacts` jsonb, `status`; delete blocked while referenced.

### DB-CAT-004 MedicineCategory
`name`, `parent_id` self-FK (acyclic enforced), `sort_order`, `status`; unique `(parent_id, name)`.

### DB-CAT-005 Unit
`name`, `symbol`, `unit_type` enum(COUNT/WEIGHT/VOLUME), `allows_fraction` bool, `status`; delete blocked while referenced.

### DB-CAT-006 MedicineUnitConversion
| Field | Type | Req | Rules |
|---|---|---|---|
| `medicine_id`, `unit_id` | fk | ✔ | Unique pair |
| `factor_to_base` | num(18,6) | ✔ | > 0; exact decimal |
| `is_purchase_default`, `is_sale_default` | bool | ✔ | At most one default each (partial unique) |
**Validation:** factors form a DAG to base unit with base = 1 (FR-UNIT-004); changing a factor is audited and blocked once the medicine has stock movements (price/unit integrity).

### DB-CAT-007 MedicineBarcode
`medicine_id`, `barcode` unique, `type` enum(PRIMARY/ALT), timestamps; lookup index `(barcode)`.

---

## Entity ↔ Use Case Map (this file)

| Entity | Primary UCs |
|---|---|
| User, Role, Permission, UserRole, RolePermission, UserBranch, Session, LoginAttempt, PasswordHistory | UC-AUTH-001…006, UC-USER-001…004, UC-RBAC-001/002 |
| Branch | UC-BRANCH-001/002 |
| Medicine, Generic, Manufacturer, MedicineCategory, MedicineBarcode | UC-CAT-001…005, UC-DOC-002 (mapping target) |
| Unit, MedicineUnitConversion | UC-UNIT-001 |
