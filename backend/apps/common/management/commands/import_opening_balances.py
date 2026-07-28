"""Import opening customer receivables and supplier payables as OPENING ledger entries."""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from apps.branches.models import Branch
from apps.common.management.commands._import_utils import ImportReport, read_rows
from apps.sales.models import Customer, CustomerLedgerEntryType
from apps.sales.services import post_customer_ledger_entry
from apps.suppliers.models import Supplier, SupplierLedgerEntryType
from apps.suppliers.services import post_ledger_entry


class Command(BaseCommand):
    help = "Import opening balances from CSV (see docs/import-templates/opening-balances.csv)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["file"])
        dry_run = options["dry_run"]
        report = ImportReport()

        for index, row in enumerate(rows, start=2):
            entity_type = (row.get("entity_type") or "").upper()
            code = (row.get("code") or "").upper()
            branch = Branch.objects.filter(code=(row.get("branch_code") or "").upper()).first()
            if entity_type not in ("CUSTOMER", "SUPPLIER"):
                report.error(index, "entity_type must be CUSTOMER or SUPPLIER")
                continue
            if branch is None:
                report.error(index, f"branch not found: {row.get('branch_code')}")
                continue
            try:
                amount = Decimal(row.get("amount") or "0")
            except InvalidOperation as exc:
                report.error(index, f"invalid amount: {exc}")
                continue
            if amount <= 0:
                report.error(index, "amount must be positive")
                continue

            if entity_type == "CUSTOMER":
                customer = Customer.objects.filter(code=code).first()
                if customer is None:
                    report.error(index, f"customer not found: {code}")
                    continue
                key = f"opening-import:customer:{customer.id}"
                if customer.ledger_entries.filter(idempotency_key=key).exists():
                    report.skipped += 1
                    continue
                report.created += 1
                if not dry_run:
                    post_customer_ledger_entry(
                        customer=customer,
                        branch=branch,
                        entry_type=CustomerLedgerEntryType.OPENING,
                        amount_delta=amount,
                        source_type="OPENING_IMPORT",
                        source_number="OPENING",
                        idempotency_key=key,
                    )
            else:
                supplier = Supplier.objects.filter(code=code).first()
                if supplier is None:
                    report.error(index, f"supplier not found: {code}")
                    continue
                key = f"opening-import:supplier:{supplier.id}"
                if supplier.ledger_entries.filter(idempotency_key=key).exists():
                    report.skipped += 1
                    continue
                report.created += 1
                if not dry_run:
                    post_ledger_entry(
                        supplier=supplier,
                        branch=branch,
                        entry_type=SupplierLedgerEntryType.OPENING,
                        amount_delta=amount,
                        source_type="OPENING_IMPORT",
                        source_number="OPENING",
                        idempotency_key=key,
                    )

        report.finish(self, dry_run)
