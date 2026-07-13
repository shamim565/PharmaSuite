# Functional Requirements — Catalog & Units

**Document ID:** DOC-FR-02
**Parent:** `docs/01-requirements-specification.md`
**Priority tags:** M = MVP must · S = MVP should · P2 = Phase 2 · FUT = future

---

## FR-CAT — Medicine Catalog (Generics, Manufacturers, Categories, Medicines)

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-CAT-001 | Create/edit/soft-delete medicine records with brand name, unique item code, generic, manufacturer, category, dosage form, strength, pack description | WM/Adm | M | Required fields enforced; duplicate item code rejected |
| FR-CAT-002 | Store multiple identifiers per medicine: manufacturer code, primary and alternate barcodes | WM | M | Barcode lookup returns the medicine; duplicates warned |
| FR-CAT-003 | Store standard prices: trade price, MRP, retail, wholesale, custom tier, and read-only last purchase cost (system-maintained) | Adm/Acct | M | Manual edit of last purchase cost is impossible |
| FR-CAT-004 | Flag "prescription required" per medicine, with configurable Rx reference requirement at sale | Adm | M | Invoice warns or requires Rx reference per setting (A-…, Q-027) |
| FR-CAT-005 | Flag controlled/narcotic (schedule) class; sales of flagged items require `SALE_CONTROLLED` permission and are reported | Adm | M | Unauthorized sale blocked and audited; controlled-sales report available |
| FR-CAT-006 | Store storage condition (ambient / cool / cold-chain) and handling notes | WM | M | Cold-chain medicines identifiable in lists and reports |
| FR-CAT-007 | Store default shelf-life months and per-medicine near-expiry warning threshold (fallback to company default) | Adm | M | Batch creation suggests expiry; alerts use the threshold |
| FR-CAT-008 | Store VAT rate per medicine (0/5/10/15, default 15); VAT computed on discounted net line value | Adm | M | Invoice tax totals reconcile with line rates |
| FR-CAT-009 | Link medicine to its unit/pack conversion set (see FR-UNIT) | WM | M | Purchases/sales in any conversion unit update base-unit stock correctly |
| FR-CAT-010 | Medicine lifecycle status: active / inactive / discontinued, with effective date; discontinued blocks new purchases, allows sales of remaining stock | Adm | M | Discontinued item cannot be added to new purchases |
| FR-CAT-011 | Upload medicine image/thumbnail | Adm | S | Image stored in object storage; size/type validated |
| FR-CAT-012 | Search medicines by brand, generic, manufacturer, category, code, barcode, alias/synonym | All | M | Typeahead returns results < 300 ms p95; barcode scan-ready endpoint |
| FR-CAT-013 | Medicine list filters: category, manufacturer, generic, status, stock position, expiry position, branch | All | M | Filter combinations are composable and URL-shareable |
| FR-CAT-014 | Import catalog from CSV template with validation report; export filtered catalog | Adm | S | Row-level errors reported; import is transactional per file |
| FR-CAT-015 | Merge duplicate medicines: blocked if both have stock/transactions; otherwise remaps mappings and deactivates duplicate | Adm | S | Merge audited; stock/report continuity preserved |
| FR-CAT-016 | Generic-name CRUD (name, therapeutic class, description, status) | Adm | M | Generic deletion blocked while medicines reference it |
| FR-CAT-017 | Manufacturer CRUD (name, country, contact, license info, status) | Adm | M | Manufacturer deletion blocked while medicines reference it |
| FR-CAT-018 | Category CRUD as hierarchy (parent/child, sort order, status) | Adm | M | Cycle creation rejected; lists show breadcrumb |
| FR-CAT-019 | Record medicine attributes: dosage form, strength, pack size, flavor/coating, route | WM | M | Attributes appear on invoices/reports where configured |
| FR-CAT-020 | Suggest substitute medicines by same generic+strength (for out-of-stock cases) | SO | S | Suggestion list available from sale line; substitutions logged |
| FR-CAT-021 | Reorder level (min stock) per medicine per branch; drives low-stock alerts and reports | WM/BM | M | Alerts trigger when available stock ≤ reorder level |
| FR-CAT-022 | Preferred supplier per medicine (default on purchase entry) | WM | S | Purchase line pre-fills preferred supplier when creating a supplier-grouped purchase |
| FR-CAT-023 | View price-change history per medicine (who/when/old/new) | Adm/Acct | S | History derives from audit trail; read-only |
| FR-CAT-024 | Configure minimum margin % per medicine/category; sale below floor warns or blocks per permission | Adm | M | Margin guard evaluated at sale; overrides reported |
| FR-CAT-025 | Cold-chain register: list cold-chain medicines with current batch stock and expiry | WM | S | Exportable for compliance |
| FR-CAT-026 | Flag items that do not require batch/expiry (consumables) — exempt from batch rules | Adm | M | Such items skip batch selection and expiry validation |
| FR-CAT-027 | Control-class warning printed on invoice for Rx/controlled items | Sys | S | Invoice template shows the warning when applicable |
| FR-CAT-028 | Custom key-value attributes per medicine for future needs | Adm | P2 | Not scheduled |

## FR-UNIT — Units & Pack Conversions

| ID | Requirement | Actor | Pri | Acceptance criteria |
|---|---|---|---|---|
| FR-UNIT-001 | Unit CRUD: name, symbol, type (count/weight/volume), allows-fraction flag | Adm | M | Unit in use cannot be deleted |
| FR-UNIT-002 | Assign a base unit per medicine (stock is always kept in base units) | WM | M | All ledger quantities stored in base units |
| FR-UNIT-003 | Define pack conversions (e.g., 1 box = 10 strips; 1 strip = 10 tablets) | WM | M | Conversion factors stored as exact decimals |
| FR-UNIT-004 | Validate conversions: positive factors, no cycles, base factor exactly 1; conversions only to smaller units or nested packs | Sys | M | Invalid sets rejected with clear errors |
| FR-UNIT-005 | Purchase entry in any allowed purchase unit (box/strip); system converts to base units for stock and cost | WM | M | Line qty × factor equals posted base qty exactly |
| FR-UNIT-006 | Sale entry in any allowed sale unit with correct price resolution: price per selected unit or derived from base price with rounding rule | SO | M | Totals match unit price × qty rounded per BR-DATA rules |
| FR-UNIT-007 | Display human-friendly breakdown on documents (e.g., "2 boxes 3 strips") alongside base quantity where helpful | Sys | S | Invoice and stock views consistent |
| FR-UNIT-008 | Fractional quantities allowed only when the unit's `allows_fraction` is true; otherwise whole numbers only | Sys | M | Validation rejects 0.5 tablet when not allowed |

---

*Cross-references: BR-INV-* (batch/stock rules), BR-PUR-002 (bonus costing), pricing rules in `08-business-rules.md`.*
