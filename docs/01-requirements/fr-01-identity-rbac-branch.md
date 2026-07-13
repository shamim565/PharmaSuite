# Functional Requirements — Identity, Users, RBAC, Branches

**Document ID:** DOC-FR-01
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future
**Actor legend:** All = any authenticated user · Owner · SA = Super Admin · Adm = Admin · Acct = Accountant · SO = Sales Operator · WM = Warehouse Manager · BM = Branch Manager · SR = Sales Rep · MR = Medical Rep · Sys = system (Celery/automation)

---

## FR-AUTH — Authentication & Sessions

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-AUTH-001 | Sign in with mobile number **or** email plus password | All | M | Valid credentials establish a session; invalid returns a single generic error |
| FR-AUTH-002 | Invalid-credential responses must not reveal whether the account exists | All | M | Same message/timing class for unknown user vs wrong password |
| FR-AUTH-003 | Lock account after N failed attempts (default 5 in 15 min, configurable); auto-unlock after 15 min or admin unlock | Sys/SA | M | Further attempts return `ACCOUNT_LOCKED`; unlock is audited |
| FR-AUTH-004 | Enforce password policy: min 8 chars, upper+lower+digit (configurable), no spaces-only | All | M | Weak passwords rejected with field errors |
| FR-AUTH-005 | Self-service password reset via single-use token sent by email/SMS; 15-min expiry | All | M | Token use is single; expired/used tokens rejected |
| FR-AUTH-006 | Force password change on first login and after admin reset | All | M | All routes blocked until password changed |
| FR-AUTH-007 | Change own password by supplying current password | All | M | Wrong current password rejected; event audited |
| FR-AUTH-008 | Prevent reuse of the last 5 passwords | All | S | Change rejected with policy message |
| FR-AUTH-009 | Issue short-lived JWT access token (default 15 min) and rotating refresh token stored in an httpOnly, Secure, SameSite cookie | Sys | M | Tokens never exposed to JS storage; refresh works across PWA restarts |
| FR-AUTH-010 | Refresh rotation with reuse detection; a reused refresh token revokes its whole session family | Sys | M | Replay of old refresh token forces re-login and raises a security event |
| FR-AUTH-011 | Logout current session and revoke its tokens | All | M | Refresh token invalid immediately after logout |
| FR-AUTH-012 | Logout all devices; administrators can force-logout a specific user | All/SA | M | All refresh tokens for the user are revoked |
| FR-AUTH-013 | List active sessions/devices (label, IP, last active, created) with per-session revoke | All | S | Current session flagged; revoke takes effect immediately |
| FR-AUTH-014 | Idle timeout (default 30 min, configurable) requiring re-authentication | All | M | Idle UI redirects to login; unsaved form warning where feasible |
| FR-AUTH-015 | Optional TOTP 2FA, mandatory for Owner/Admin when enabled at company level; one-time recovery codes | Adm+ | M | Login requires valid TOTP; recovery code single-use |
| FR-AUTH-016 | Log every authentication event (success, failure, lockout, reset, 2FA) with IP/user-agent | Sys | M | Events visible in login history/audit |
| FR-AUTH-017 | Rate-limit sign-in and reset attempts per account and per IP (Redis-backed) | Sys | M | Excess attempts return `TOO_MANY_REQUESTS` with retry-after |
| FR-AUTH-018 | Configurable concurrent-session policy: allow multi-device (default) or single active session; may differ for back-office roles | SA | S | Policy enforced at token issuance |
| FR-AUTH-019 | Optional OIDC/SSO sign-in (Google Workspace / Microsoft Entra) | All | FUT | Not scheduled |
| FR-AUTH-020 | "Remember this device" to skip 2FA for 30 days per device | All | P2 | Not scheduled |

## FR-USER — User Management

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-USER-001 | Create user with name, unique mobile, unique email, role(s), branch(es), default branch | Adm+ | M | Duplicate mobile/email rejected with field errors |
| FR-USER-002 | Invite-based activation: user receives link/SMS and sets own password | Adm+ | M | Invitation expires in 72 h; can be re-sent |
| FR-USER-003 | Admin password reset with force-change at next login | Adm+ | M | Reset audited; old sessions revoked |
| FR-USER-004 | Activate/deactivate users; deactivated users cannot authenticate and all sessions are revoked | Adm+ | M | API access immediately denied |
| FR-USER-005 | Soft-delete users with history; hard delete only never-used accounts | Owner/SA | M | Deleted user still appears in historical documents |
| FR-USER-006 | Edit own profile (name, avatar, language); mobile/email changes require admin approval | All/Adm | S | Changed contact is audited |
| FR-USER-007 | Assign multiple roles; effective permissions are the union with deny precedence | Adm+ | M | Preview shows final permission set before save |
| FR-USER-008 | Assign branch access set and default branch | Adm+ | M | User without branches sees no operational data |
| FR-USER-009 | Block deactivation/deletion of self and of the last active Owner | Sys | M | Action rejected with explanatory error |
| FR-USER-010 | User directory with search (name/mobile/email) and filters (role, branch, status) | Adm+ | M | Results respect branch scoping |
| FR-USER-011 | Bulk user import from CSV template with per-row validation report | Adm+ | S | Invalid rows reported; valid rows imported transactionally |
| FR-USER-012 | Mask staff contact details from roles lacking `USER_VIEW_CONTACT` | Sys | S | Masked at API level, not just UI |
| FR-USER-013 | Per-user activity summary: last login, active sessions, recent audited actions | Adm+ | S | Links resolve to audit log filtered by actor |
| FR-USER-014 | Mark an account "locked — no self-service reset" for terminated/suspended staff | Adm+ | S | Reset requests are refused |
| FR-USER-015 | Any user can view and edit their own profile page | All | M | No access to others' profiles without permission |

## FR-RBAC — Roles & Permissions

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-RBAC-001 | Maintain a versioned permission catalog grouped by module and action (view/create/edit/confirm/cancel/approve/export/override) | Sys | M | Catalog is code-managed; permissions are stable IDs |
| FR-RBAC-002 | Role CRUD; system roles protected from deletion (cloneable only) | SA | M | System role edits limited to permission grants, never code identity |
| FR-RBAC-003 | Grant/deny individual permissions per role; explicit deny overrides grant | SA | M | Effective-permission computation is deterministic and unit-tested |
| FR-RBAC-004 | Role carries a branch scope (`all_branches` vs `assigned_only`) | SA | M | Scope enforced on every queryset |
| FR-RBAC-005 | Clone a role as a starting point for custom roles | SA | S | Clone records source role for audit |
| FR-RBAC-006 | No privilege escalation: an actor cannot grant permissions they do not hold (Owner exempt) | Sys | M | Attempt returns `PERMISSION_ESCALATION_BLOCKED` |
| FR-RBAC-007 | Every API endpoint enforces permissions server-side (default deny) | Sys | M | Security tests cover every endpoint; UI checks are additive only |
| FR-RBAC-008 | Navigate/route/button visibility derived from effective permissions; hidden ≠ allowed | Sys | M | Direct API calls still enforced when UI is hidden |
| FR-RBAC-009 | Branch-scoped object permissions: records outside assigned branches behave as not found | Sys | M | IDOR test suite passes for all document types |
| FR-RBAC-010 | Field-level masking of cost/profit fields for roles without `VIEW_COST`/`VIEW_PROFIT` | Sys | M | Masking applied in serializers, verified by API tests |
| FR-RBAC-011 | Configurable approval thresholds per permission: discounts, credit override, write-off, backdate, period override | SA | M | Exceeding threshold routes to an approver or blocks |
| FR-RBAC-012 | Preview effective permissions for a user before saving role/assignment changes | SA | S | Preview matches runtime evaluation |
| FR-RBAC-013 | Audit every role, permission, and assignment change with before/after values | Sys | M | Entries immutable and searchable |
| FR-RBAC-014 | Dual-control option for high-risk actions (period override, write-off above threshold): a second authorized user must approve | SA | S | Request stays pending until second approval; both users audited |
| FR-RBAC-015 | Export the role–permission matrix for internal/external audit | SA | S | Export reflects runtime catalog version |

## FR-BRANCH — Multi-Branch

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-BRANCH-001 | Branch CRUD: unique code, name, address, phones, manager, opening date | SA/Owner | M | Duplicate code rejected |
| FR-BRANCH-002 | Store branch legal/tax details (BIN/VAT reg, trade license, invoice prefixes) | SA | M | Used on invoices/reports for that branch |
| FR-BRANCH-003 | All operational documents carry `branch_id`; stock, ledgers, accounts and sequences are branch-scoped | Sys | M | Cross-branch leakage tests pass |
| FR-BRANCH-004 | Assign users to branches; default branch applied at login | Adm+ | M | Login lands in default branch context |
| FR-BRANCH-005 | Branch switcher for multi-branch users with persistent context indicator | All | M | Switching refreshes scoped data; no mixed-branch views |
| FR-BRANCH-006 | Mark one branch as Head Office; HO users may consolidate all branches | SA | M | Consolidation requires `all_branches` scope |
| FR-BRANCH-007 | Block branch deactivation while stock, open receivables/payables, or account balances exist | Sys | M | Error lists blocking conditions |
| FR-BRANCH-008 | Branch settings inherit company defaults with explicit overrides | SA | M | Overridden fields visibly flagged |
| FR-BRANCH-009 | Branch detail page with KPIs: stock value, today's sales/collection, dues, payables | BM+ | M | Figures match reports for the same date |
| FR-BRANCH-010 | Consolidated reports across branches (permission-gated, never for assigned-only roles) | Owner/Adm | M | Branch comparison shows per-branch and total columns |
| FR-BRANCH-011 | Audit all branch lifecycle events | Sys | M | Create/edit/deactivate entries in audit log |
| FR-BRANCH-012 | No access to unassigned branches through any URL, ID, export or report parameter | Sys | M | Automated IDOR tests for branch parameters pass |

---

*Cross-references: BR-AUTH-* and BR-RBAC-* in `docs/01-requirements/08-business-rules.md`; edge cases for concurrent sessions and branch isolation are analyzed in Phase 2.*
