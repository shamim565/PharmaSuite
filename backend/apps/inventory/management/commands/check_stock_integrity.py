from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import MedicineBatch
from apps.inventory.models import StockBalance
from apps.inventory.services import ledger_quantities


class Command(BaseCommand):
    help = "Reconcile cached stock balances and batch quantities against the inventory ledger."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Repair cached balances from the ledger instead of only reporting.",
        )

    def handle(self, *args, **options):
        repair = options["repair"]
        mismatches = 0
        repaired = 0

        for balance in StockBalance.objects.select_related("branch", "medicine", "batch"):
            totals = ledger_quantities(balance.branch, balance.medicine, balance.batch)
            if (
                totals["SALEABLE"] != balance.qty_on_hand
                or totals["PROMO"] != balance.qty_promo
                or totals["QUARANTINE"] != balance.qty_quarantine
            ):
                mismatches += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"balance mismatch: {balance.medicine.code} / {balance.batch.batch_number} "
                        f"cached(saleable={balance.qty_on_hand}, promo={balance.qty_promo}, "
                        f"quarantine={balance.qty_quarantine}) "
                        f"ledger(saleable={totals['SALEABLE']}, promo={totals['PROMO']}, "
                        f"quarantine={totals['QUARANTINE']})"
                    )
                )
                if repair:
                    balance.qty_on_hand = totals["SALEABLE"]
                    balance.qty_promo = totals["PROMO"]
                    balance.qty_quarantine = totals["QUARANTINE"]
                    balance.version += 1
                    balance.save(update_fields=["qty_on_hand", "qty_promo", "qty_quarantine", "version", "updated_at"])
                    repaired += 1

        batch_cache_mismatches = 0
        for batch in MedicineBatch.objects.all():
            balance = StockBalance.objects.filter(batch=batch).first()
            ledger_total = ledger_quantities(batch.branch, batch.medicine, batch)
            expected = ledger_total["SALEABLE"]
            if (batch.qty_on_hand or Decimal("0")) != expected:
                batch_cache_mismatches += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"batch cache mismatch: {batch.medicine.code} / {batch.batch_number} "
                        f"batch={batch.qty_on_hand} ledger={expected}"
                    )
                )
                if repair:
                    batch.qty_on_hand = expected
                    batch.save(update_fields=["qty_on_hand", "updated_at"])
                    repaired += 1

        if mismatches == 0 and batch_cache_mismatches == 0:
            self.stdout.write(self.style.SUCCESS("Stock integrity OK — balances and batch caches match the ledger."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {mismatches} balance mismatch(es), {batch_cache_mismatches} batch cache "
                    f"mismatch(es). Repaired: {repaired}."
                )
            )
