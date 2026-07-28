"""Import opening cash/bank/MFS balances as OPENING account transactions."""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from apps.accounting.models import FinancialAccount, FinancialTransaction
from apps.common.management.commands._import_utils import ImportReport, read_rows


class Command(BaseCommand):
    help = "Import opening account balances from CSV (see docs/import-templates/opening-accounts.csv)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["file"])
        dry_run = options["dry_run"]
        report = ImportReport()

        for index, row in enumerate(rows, start=2):
            account = FinancialAccount.objects.filter(code=(row.get("account_code") or "").upper()).first()
            if account is None:
                report.error(index, f"account not found: {row.get('account_code')}")
                continue
            try:
                amount = Decimal(row.get("amount") or "0")
            except InvalidOperation as exc:
                report.error(index, f"invalid amount: {exc}")
                continue
            if amount <= 0:
                report.error(index, "amount must be positive")
                continue

            key = f"opening-import:account:{account.id}"
            if FinancialTransaction.objects.filter(idempotency_key=key).exists():
                report.skipped += 1
                continue

            report.created += 1
            if dry_run:
                continue

            from apps.accounting.services import post_account_transaction

            post_account_transaction(
                account=account,
                entry_type="OPENING",
                amount_delta=amount,
                source_type="OPENING_IMPORT",
                source_number="OPENING",
                reference=row.get("note", ""),
                idempotency_key=key,
            )

        report.finish(self, dry_run)
