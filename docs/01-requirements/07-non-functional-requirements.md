# Non-Functional Requirements

**Document ID:** DOC-NFR-001
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future
**Verification:** each NFR states how it will be verified (test type in brackets).

---

## NFR-SEC — Security

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-SEC-001 | All client-server traffic uses TLS 1.2+ with HSTS; HTTP redirected; cookies `Secure`, `HttpOnly`, `SameSite` | M | Infra test + header scan |
| NFR-SEC-002 | Passwords hashed with Argon2id; JWT access/refresh per A-008; secrets only in a secret store/env injection, never in the repository | M | Code review + secret scan in CI |
| NFR-SEC-003 | OWASP Top 10 controls implemented; dependency and container scanning in CI; critical vulnerabilities patched within 7 days, high within 30 | M | CI gates + quarterly pen-test |
| NFR-SEC-004 | Rate limiting per account, IP, and endpoint class (auth stricter); brute-force lockout per FR-AUTH-003/017 | M | Security tests (TC-SEC-*) |
| NFR-SEC-005 | File uploads validated by size, extension, MIME sniffing; stored outside web root with unguessable keys; optional AV scan hook | M | Upload tests |
| NFR-SEC-006 | Encryption at rest for database volumes, backups, and object storage (provider-managed keys minimum); PII minimized per NFR-PRIV | M | Infra review |

## NFR-PERF — Performance

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-PERF-001 | API p95: reads ≤ 300 ms, writes ≤ 800 ms at baseline load; sale/purchase confirmation p95 ≤ 1.5 s | M | k6 load test in staging |
| NFR-PERF-002 | Dashboard interactive (first meaningful paint + data) ≤ 2.5 s p95 on a simulated 4G connection | M | Lighthouse + Playwright timing |
| NFR-PERF-003 | Interactive reports ≤ 2 s p95; larger reports route to async generation with notification | M | Report timing tests |
| NFR-PERF-004 | Search/typeahead p95 ≤ 300 ms at 200 concurrent users | M | Load test |
| NFR-PERF-005 | Baseline load: 100–200 concurrent users with error rate ≤ 1% and no degradation of confirmation paths | M | k6 scenario suite |

## NFR-SCALE — Scalability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-SCALE-001 | Support 1,000 users / 10 branches via vertical scaling + read replicas without re-architecture | S | Design review + capacity plan |
| NFR-SCALE-002 | Ledger tables designed for ≥ 1M rows/year/branch with monthly partitioning readiness and indexed access paths | S | Schema review + EXPLAIN tests |
| NFR-SCALE-003 | Background workers scale horizontally by adding containers; queues separated for heavy reports vs critical alerts | S | Ops test |

## NFR-REL — Reliability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-REL-001 | All financial/inventory operations are ACID; no partial postings are ever visible | M | Integration tests + fault injection |
| NFR-REL-002 | All document-creating writes are idempotent via `Idempotency-Key`; client retries are safe | M | Concurrency tests |
| NFR-REL-003 | Nightly integrity checks (ledger vs cache for stock/customer/supplier/accounts) with alerting on mismatch | M | Job test + alert drill |

## NFR-AVL — Availability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-AVL-001 | ≥ 99.5% monthly availability excluding announced maintenance, measured by external uptime probe | M | Monitoring report |
| NFR-AVL-002 | Planned maintenance announced ≥ 24 h ahead, scheduled outside business hours; zero-downtime migrations preferred | M | Change process audit |
| NFR-AVL-003 | Graceful degradation: async reports/notifications may fail soft; core sale, purchase confirmation, collection remain available; read replicas serve reports | S | Failure-mode drill |

## NFR-BAK — Backup

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-BAK-001 | Nightly full database backup + continuous WAL archiving; RPO ≤ 15 minutes | M | Backup audit + restore test |
| NFR-BAK-002 | Object storage versioning enabled; deleted/overwritten files recoverable | M | Restore test |
| NFR-BAK-003 | Backups encrypted; access restricted to designated operators; backup status alerted | M | Access review |
| NFR-BAK-004 | Configuration/secrets backed up separately with custodianship rules | S | Ops review |

## NFR-REC — Recovery

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-REC-001 | RTO ≤ 4 hours for full service restoration; DR runbook exercised quarterly | M | Quarterly DR drill |
| NFR-REC-002 | Point-in-time restore to any timestamp within 35-day retention | M | Restore test |
| NFR-REC-003 | Application rollback (previous release) completes ≤ 30 minutes with schema-compatible releases (expand/contract migrations) | M | Deployment drill |

## NFR-ACC — Accessibility

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-ACC-001 | Core flows (login, sale entry, collection, lists, forms) conform to WCAG 2.1 AA | M | axe-core automated + manual audit |
| NFR-ACC-002 | Full keyboard navigation with visible focus; form fields programmatically labeled for screen readers | M | Manual audit |
| NFR-ACC-003 | Contrast ≥ 4.5:1 for text; errors conveyed by text/icon, never color alone | M | Automated audit |

## NFR-MOB — Mobile Responsiveness & PWA

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-MOB-001 | Usable at 360 px–1920 px; touch targets ≥ 44 px; no horizontal scrolling on core flows | M | Device lab tests |
| NFR-MOB-002 | Installable PWA: manifest, service worker, app shell, offline read of recently viewed lists; writes are retry-safe (idempotent), never queued offline (DEC-005) | M | PWA audit + offline tests |
| NFR-MOB-003 | Performance budgets: initial route JS ≤ 250 KB gzip for core flows; images optimized (WebP) | S | Lighthouse CI |
| NFR-MOB-004 | Mobile-first flows for sale entry, payment collection, doctor visits, stock check, dashboard | M | UAT scenarios |

## NFR-MAINT — Maintainability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-MAINT-001 | Modular monolith with enforced module boundaries (no circular imports), service layer owns business rules | M | import-linter in CI |
| NFR-MAINT-002 | Quality gates: lint, typecheck (mypy/TypeScript strict), tests, coverage thresholds; mandatory code review | M | CI pipeline |
| NFR-MAINT-003 | API versioning with deprecation policy: `/api/v1` supported minimum 6 months after successor version | M | API governance |
| NFR-MAINT-004 | ADRs recorded for significant decisions; documentation updated at each phase gate | S | Documentation review |

## NFR-LOG — Logging

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-LOG-001 | Structured JSON application logs with request id, actor, branch, route, latency, status | M | Log inspection |
| NFR-LOG-002 | No secrets, tokens, passwords, or full PII in logs; redaction middleware tests | M | Automated redaction tests |
| NFR-LOG-003 | Central retention: 90 days hot, 12 months cold; log access restricted | S | Retention policy review |

## NFR-OBS — Observability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-OBS-001 | Metrics: request latency/error rates, DB saturation, Redis memory, queue depth, business KPIs (sales/min, failed confirmations) | M | Dashboard review |
| NFR-OBS-002 | Health endpoints (liveness/readiness), external uptime probe, error tracking (Sentry), alert routing to on-call | M | Alert drill |
| NFR-OBS-003 | Severity-based runbooks for alerts (P1–P3) with escalation | M | Runbook audit |
| NFR-OBS-004 | Request id propagates API → Celery task → DB log context for end-to-end tracing | S | Trace test |

## NFR-AUD — Auditability

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-AUD-001 | Every critical operation (pricing, discounts, stock, payments, returns, cancellations, permission changes, period locks) is audit-logged per FR-AUD-001 | M | Audit coverage tests |
| NFR-AUD-002 | Audit queries (entity, actor, date) respond ≤ 2 s p95; storage append-only | M | Performance test |
| NFR-AUD-003 | Audit exports include a hash manifest enabling tamper detection | S | Compliance review |

## NFR-DI — Data Integrity

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-DI-001 | Monetary and quantity fields use exact decimal types only (`NUMERIC`); no floating point in code paths handling money/qty | M | Schema + code audit |
| NFR-DI-002 | Referential integrity enforced by foreign keys; non-negative quantity/amount check constraints on ledgers and balances | M | Migration audit + constraint tests |
| NFR-DI-003 | Unique constraints: master codes, batch key (branch+medicine+batch+expiry), document numbers, idempotency keys, pending allocations | M | Constraint tests |
| NFR-DI-004 | Ledgers are append-only; deletions are soft or void; corrections are compensating entries; nightly reconciliation verifies derived caches | M | Integration tests |

## NFR-PRIV — Privacy

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-PRIV-001 | Collect minimal personal data (staff, customers, doctors) with documented purpose; no clinical diagnosis data | M | Data inventory review |
| NFR-PRIV-002 | PII access restricted by role and audited; non-production environments use masked/synthetic data | M | Access review + seeding policy |
| NFR-PRIV-003 | Data-subject requests (export/correction) handled operationally; erasure only where not blocked by financial retention (7 years) | S | Procedure test |

## NFR-CMP — Browser & Device Compatibility

| ID | Requirement | Pri | Verification |
|---|---|---|---|
| NFR-CMP-001 | Supported: last 2 stable versions of Chrome, Edge, Safari, Firefox on desktop | M | Browser matrix tests |
| NFR-CMP-002 | Supported: current and previous iOS Safari and Android Chrome | M | Device lab tests |
| NFR-CMP-003 | Unsupported browsers show a clear upgrade message; PWA features degrade gracefully | S | Manual check |
| NFR-CMP-004 | Server-side PDF generation produces consistent A4/A5 output on common printers | M | Print QA |

---

## Verification Plan Summary

| NFR category | Primary verification | Phase |
|---|---|---|
| SEC, PRIV, AUD | Security test suite, pen-test, audit coverage tests | 9 |
| PERF, SCALE, AVL | k6 load tests, capacity review | 9, 10 |
| REL, DI | Integration/concurrency tests, reconciliation jobs | 9 |
| BAK, REC, OBS, LOG | DR drills, monitoring review, restore tests | 10, 12, 13 |
| ACC, MOB, CMP | axe-core, device lab, Lighthouse, PWA audit | 9 |
| MAINT | CI gates, import-linter, ADR review | 8, 13 |

*Cross-references: BR-DATA-* (rounding), BR-AUD-* (audit rules), A-024/A-028 (baseline scale and backup assumptions).*
