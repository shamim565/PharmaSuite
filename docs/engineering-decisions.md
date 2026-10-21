# Engineering decisions

Short decision records for the choices that shape PharmaSuite. Each entry states
the context, the decision, the trade-off, and the consequence. These are the
answers to "why is it built this way?" in code review or an interview.

---

## ADR-001 — Modular monolith, not microservices

**Context.** The domain spans inventory, sales, purchasing, payments, accounting,
and CRM. A single invoice confirmation must write stock, customer, and cash effects
together.

**Decision.** One Django project with one app per domain and a shared service layer.

**Trade-off.** No independent scaling or deployment per domain. In exchange, one
transaction can span stock and money, and there is one deployment target.

**Consequence.** Cross-domain consistency is a database transaction, not a saga.
Extraction is possible later along app boundaries if a domain genuinely needs it.

---

## ADR-002 — Append-only ledgers plus projection tables

**Context.** Balances must be auditable and correct after reversals, returns, and
back-dated entries. Mutating a `balance` column in place loses history.

**Decision.** Store `InventoryTransaction`, `CustomerLedgerEntry`,
`SupplierLedgerEntry`, and `FinancialTransaction` as append-only rows. Maintain
`StockBalance`, `Customer.balance_cache`, `Supplier.balance_cache`, and
`FinancialAccount.balance_cache` as queryable projections, updated in the same
transaction.

**Trade-off.** Two writes per operation and the possibility of drift. Reversals are
new rows referencing the original, never deletes.

**Consequence.** `check_stock_integrity` and `check_ledger_integrity` can prove the
projections match the ledgers. Reports read projections; audits read history.

---

## ADR-003 — Pessimistic locking on confirmation paths

**Context.** Two operators can confirm documents for the same batch or customer at
the same time. Optimistic retries would push conflict handling into every caller.

**Decision.** `select_for_update()` on the invoice, customer, batch, balance, and
account rows inside `@transaction.atomic` service functions.

**Trade-off.** Hot rows serialise, so throughput per SKU is bounded by lock hold
time. Deadlock risk is reduced by ordering inventory lines by medicine/batch id.

**Consequence.** Correctness is easy to reason about; very hot SKUs will need
partitioning or queueing before they need a different concurrency model.

---

## ADR-004 — Idempotency keys on every mutating document

**Context.** Mobile clients and reverse proxies retry. A duplicated confirmation
would double stock and receivables.

**Decision.** Each document table has a nullable, unique `idempotency_key`. Services
return the existing document when the key is reused, and inventory posting handles
the unique-constraint race by returning the canonical rows.

**Trade-off.** An extra unique index and a rule that callers must supply stable
keys. Keys are optional for UI-created drafts, required for retryable operations.

**Consequence.** Retries are safe by construction. Tests cover concurrent same-key
posting (`test_concurrent_same_key_*`).

---

## ADR-005 — `Decimal` for money and quantity, everywhere

**Context.** Binary floats cannot represent 0.10 exactly. Distribution margins are
thin and discrepancies compound across invoices and returns.

**Decision.** `DecimalField` in models, `Decimal` in services, explicit quantisation
at boundaries (`money()` to 2 places, `cost4()` to 4).

**Trade-off.** More verbose arithmetic and slower operations than floats.

**Consequence.** Totals reconcile exactly. Serializers and reports stringify
decimals rather than emitting floats.

---

## ADR-006 — Data-driven RBAC with branch scope

**Context.** A distributor has owners, accountants, branch managers, warehouse
staff, sales operators, and field reps. Permissions differ by role and by branch,
and sensitive actions need explicit grants.

**Decision.** Persist a permission catalog, roles, role-permission mappings with
ALLOW/DENY, user-role assignments, and user-branch assignments. Views declare
`required_permissions`; querysets are filtered by branch scope.

**Trade-off.** More schema and admin UI than Django groups, plus a permission cache
to invalidate on role changes.

**Consequence.** Roles are editable without a deploy; sensitive actions (cost
visibility, overrides, refunds, period unlock) are individually gated and audited.

---

## ADR-007 — Business rules in services, not views or serializers

**Context.** Confirmation flows span many models and must be reusable from the API,
management commands, and tests.

**Decision.** Views handle HTTP; serializers handle input shape; `apps/*/services.py`
owns transactions, locks, ledger postings, and audit entries.

**Trade-off.** More modules and explicit function signatures instead of convenience
methods on models.

**Consequence.** The same `confirm_sale` is exercised by the API and the test suite.
Views stay small enough to review quickly.

---

## ADR-008 — Redis for Celery only; no cache in the request path

**Context.** Balances are projections that must not go stale. A naive read-through
cache would hide posting bugs and complicate invalidation.

**Decision.** Use Redis as the Celery broker/result backend. Do not cache balances
or reports. The Django `CACHES` setting exists but no code calls it.

**Trade-off.** Reports recompute on request; large datasets will need materialised
views rather than a generic cache.

**Consequence.** Reads are predictable and always reflect the last committed
transaction. Documentation must not claim a caching layer.

---

## ADR-009 — Branch-scoped, fiscal-year document numbering

**Context.** Distributors need gapless, human-readable document numbers per branch
and fiscal year; duplicates destroy trust in the ledger.

**Decision.** A `DocumentSequence` row per branch, document type, and fiscal year,
locked with `select_for_update` and incremented inside the caller's transaction.

**Trade-off.** Contention on the sequence row for high-volume branches; the number
is only allocated when the document is confirmed, not when a draft is created.

**Consequence.** Numbers can have gaps when a transaction rolls back, which is
preferable to duplicates and is standard for accounting documents.

---

## ADR-010 — Reversals instead of deletes

**Context.** Posted financial and stock documents are evidence. Deleting them
breaks auditability and reconciliation.

**Decision.** Cancel/reverse operations create compensating ledger rows and mark the
document status; they never delete posted entries.

**Trade-off.** More rows and more status transitions to reason about.

**Consequence.** Every balance remains derivable from history, and the audit log can
show who reversed what, when, and why.
