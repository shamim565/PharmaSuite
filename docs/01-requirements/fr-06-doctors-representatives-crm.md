# Functional Requirements — Doctors, Doctor Visits, Representatives & Territories

**Document ID:** DOC-FR-06
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-DOC — Doctors & Doctor–Medicine Mapping

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-DOC-001 | Doctor CRUD: name, unique code, gender, multiple phones, email, specialty, degrees, type (consultant/GP/others) | MR/Adm | M | Required fields enforced |
| FR-DOC-002 | BMDC/registration number stored and unique when provided | Adm | M | Duplicate registration rejected |
| FR-DOC-003 | Multiple chamber/hospital affiliations per doctor (name, address, visiting hours) | MR | M | Visible on visit planning screen |
| FR-DOC-004 | Doctor category/segment (A/B/C) and potential rating | BM/MR | M | Used in coverage and targeting reports |
| FR-DOC-005 | Doctor assigned to a territory/area | BM | M | Territory reports populate |
| FR-DOC-006 | Assign one or more MRs responsible for the doctor, with effective dates | BM | M | Coverage reports use current assignment |
| FR-DOC-007 | Doctor–medicine mapping: which medicines are promoted to this doctor, with notes and effective dates | MR/BM | M | Mapping list printable for the MR's bag |
| FR-DOC-008 | Mapping supports strength/form and promotional priority notes | MR | S | Notes visible on doctor detail and visit log |
| FR-DOC-009 | Mapping history with who/when/before/after (audit) | Sys | M | Read-only history tab |
| FR-DOC-010 | Doctor list search (name/phone/BMDC/specialty) and filters (area, category, MR, status, last visit) | All | M | Exportable |
| FR-DOC-011 | Doctor detail tabs: profile, mappings, visits, samples, attributed sales | All | M | Permissions per tab |
| FR-DOC-012 | Attributed sales report per doctor (based on invoice doctor references) | BM/Adm | M | Filterable by medicine/period/branch |
| FR-DOC-013 | Sample distribution history per doctor with medicine, qty, batch, MR, date | MR/BM | M | Reconciles with promotional stock issues |
| FR-DOC-014 | Deactivate/reactivate doctors; soft delete only | Adm | M | Deactivated doctors excluded from new visits |
| FR-DOC-015 | Duplicate warning and merge (blocked when visits/sales exist on both) | Adm | S | Audited |
| FR-DOC-016 | Import/export doctors via CSV template with validation | Adm | S | Row-level error report |
| FR-DOC-017 | Birthday/anniversary date fields with reminder hooks | MR | P2 | Not scheduled |
| FR-DOC-018 | Consent/privacy note fields for personal data | Adm | S | Stored with doctor record |
| FR-DOC-019 | Visit frequency target per doctor (e.g., monthly) | BM | S | Feeds coverage compliance report |
| FR-DOC-020 | Free-text notes per doctor with author/time | MR | M | Notes append-only, audited |
| FR-DOC-021 | Doctor type drives default visit planning cadence | BM | P2 | Not scheduled |
| FR-DOC-022 | External reference fields (hospital IDs, others) | Adm | P2 | Not scheduled |
| FR-DOC-023 | Custom tags per doctor for campaigns | BM | P2 | Not scheduled |
| FR-DOC-024 | Full audit of doctor record and mapping changes | Sys | M | Immutable entries |

## FR-DVIS — Doctor Visits & Sample Distribution

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-DVIS-001 | Plan visits: doctor, MR, planned date/time, purpose, priority | MR/BM | M | Planned visits appear in calendar/list |
| FR-DVIS-002 | Log visit: actual date/time, doctor, MR, products discussed (from mapping), samples given, outcome/interest, next visit date, notes | MR | M | Required fields enforced; outcome from configurable list |
| FR-DVIS-003 | Sample issue deducts promotional stock and links medicine, batch, quantity to the doctor visit | MR | M | Promo stock balance decreases; history visible per doctor |
| FR-DVIS-004 | Visit list filters: date range, MR, doctor, territory, outcome, planned vs unplanned | All | M | Exportable |
| FR-DVIS-005 | Daily/weekly MR activity report: visits, samples, coverage, outcomes | BM/MR | M | Matches visit entries |
| FR-DVIS-006 | Coverage report: planned vs actual, visit frequency per doctor, missed visits | BM | M | Compliance % calculated |
| FR-DVIS-007 | Capture reason for missed/cancelled planned visits | MR | M | Missed visits appear in coverage report |
| FR-DVIS-008 | Attach photos/notes to a visit via presigned upload | MR | S | Type/size validated |
| FR-DVIS-009 | Edit rules: MR may edit own visit within 24 h (configurable); afterwards Admin/BM only; edits audited | Sys | M | Edit window enforced server-side |
| FR-DVIS-010 | In-app reminder for upcoming planned visits (assignment to MR) | Sys | S | Notification generated day before |
| FR-DVIS-011 | Calendar view (desktop) and agenda view (mobile) for planned visits | MR/BM | M | Same data, responsive presentations |
| FR-DVIS-012 | GPS + verification capture for visits | MR | P2 | Not scheduled |

## FR-REP — Representatives (Sales Reps & Medical Reps)

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-REP-001 | Representative CRUD: name, unique code, type (Sales Rep / MR), phone, branch, optional linked user account | Adm | M | One rep links to at most one user |
| FR-REP-002 | Activate/deactivate; soft delete when history exists | Adm | M | Deactivated reps cannot be assigned or log visits |
| FR-REP-003 | Assign territory/area coverage to a rep | BM | M | Territory reports populate |
| FR-REP-004 | Assign customers to a Sales Rep with effective dates (primary assignment) | BM | M | Defaulted on invoices; history retained |
| FR-REP-005 | Assign doctors to an MR with effective dates | BM | M | Coverage and mapping reports populate |
| FR-REP-006 | Monthly targets per rep: sales value/quantity (SR); visit counts (MR), by period | BM/Owner | S | Targets editable per month; audit |
| FR-REP-007 | Target vs achievement report per rep/period | BM | M | Achievement = invoiced sales net of returns (or collected, per report) |
| FR-REP-008 | Rep-wise sales report from invoice attribution | BM | M | Filterable by branch/period/item |
| FR-REP-009 | Rep-wise collection report from payments collected | Acct | M | Ties to daily collection report |
| FR-REP-010 | MR visit performance report (planned vs actual, coverage, samples) | BM | M | Matches visit records |
| FR-REP-011 | Assignment history (customers/doctors/territories) with dates and actor | Sys | M | Audited |
| FR-REP-012 | Primary and secondary rep assignment per customer | BM | P2 | Not scheduled |
| FR-REP-013 | Reporting hierarchy (reports-to manager) for roll-up reports | BM | S | Roll-up shows subordinate totals |
| FR-REP-014 | Performance ranking table (sales, collection, coverage) | BM | S | Configurable metric weighting |
| FR-REP-015 | Deactivation guard: require reassignment of active customers/doctors | Sys | M | Clear list of reassignment needs |
| FR-REP-016 | Export all rep reports to Excel/PDF | All | M | Honors filters |

## FR-TER — Territories

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-TER-001 | Territory hierarchy CRUD: region → area → territory | BM/Adm | M | Cycle creation rejected; hierarchy browsable |
| FR-TER-002 | Assign customers and doctors to a territory | BM | M | Assignment appears on profiles |
| FR-TER-003 | Territory-wise reports: sales, collection, visits, dues | BM | M | Roll-ups follow the hierarchy |
| FR-TER-004 | Reassignment with history (who/when) | Sys | M | Audited; past reports unchanged |
| FR-TER-005 | Deactivate territory blocked while active assignments exist | Sys | M | Error lists blocking assignments |
| FR-TER-006 | Territory map visualization | BM | P2 | Not scheduled |

---

*Cross-references: sample/promo stock rules (BR-INV, FR-INV-024), sales attribution (FR-SALE-011/012), commissions deferred per Q-039.*
