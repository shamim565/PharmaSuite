"""Verify customer/supplier/account balance caches against their append-only ledgers."""

from django.core.management.base import BaseCommand

from apps.accounting.models import FinancialAccount
from apps.accounting.services import account_ledger_balance
from apps.sales.models import Customer
from apps.sales.services import customer_balance_from_ledger
from apps.suppliers.models import Supplier
from apps.suppliers.services import supplier_balance_from_ledger


class Command(BaseCommand):
    help = "Compare cached customer/supplier/account balances with ledger sums."

    def add_arguments(self, parser):
        parser.add_argument("--repair", action="store_true", help="Repair caches from ledger sums.")

    def handle(self, *args, **options):
        repair = options["repair"]
        mismatches = 0
        repaired = 0

        for customer in Customer.objects.all():
            expected = customer_balance_from_ledger(customer)
            if customer.balance_cache != expected:
                mismatches += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"customer {customer.code}: cache={customer.balance_cache} ledger={expected}"
                    )
                )
                if repair:
                    customer.balance_cache = expected
                    customer.save(update_fields=["balance_cache", "updated_at"])
                    repaired += 1

        for supplier in Supplier.objects.all():
            expected = supplier_balance_from_ledger(supplier)
            if supplier.balance_cache != expected:
                mismatches += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"supplier {supplier.code}: cache={supplier.balance_cache} ledger={expected}"
                    )
                )
                if repair:
                    supplier.balance_cache = expected
                    supplier.save(update_fields=["balance_cache", "updated_at"])
                    repaired += 1

        for account in FinancialAccount.objects.all():
            expected = account_ledger_balance(account)
            if account.balance_cache != expected:
                mismatches += 1
                self.stdout.write(
                    self.style.WARNING(f"account {account.code}: cache={account.balance_cache} ledger={expected}")
                )
                if repair:
                    account.balance_cache = expected
                    account.save(update_fields=["balance_cache", "updated_at"])
                    repaired += 1

        if mismatches == 0:
            self.stdout.write(self.style.SUCCESS("Ledger integrity OK — all caches match ledgers."))
        else:
            self.stdout.write(
                self.style.WARNING(f"{mismatches} mismatch(es) found. Repaired: {repaired}.")
            )
