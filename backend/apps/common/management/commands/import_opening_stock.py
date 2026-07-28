"""Import opening stock as batches + OPENING ledger movements."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from apps.branches.models import Branch
from apps.catalog.models import BatchStatus, Medicine, MedicineBatch
from apps.common.management.commands._import_utils import ImportReport, read_rows
from apps.inventory.models import EntryType, InventoryTransaction
from apps.inventory.services import MovementLine, post_transactions


def parse_date(value: str):
    if not value:
        return None
    return date.fromisoformat(value)


class Command(BaseCommand):
    help = "Import opening stock from CSV (see docs/import-templates/opening-stock.csv)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["file"])
        dry_run = options["dry_run"]
        report = ImportReport()

        for index, row in enumerate(rows, start=2):
            branch = Branch.objects.filter(code=row.get("branch_code", "").upper()).first()
            medicine = Medicine.objects.filter(code=row.get("medicine_code", "").upper()).first()
            if branch is None:
                report.error(index, f"branch not found: {row.get('branch_code')}")
                continue
            if medicine is None:
                report.error(index, f"medicine not found: {row.get('medicine_code')}")
                continue
            try:
                qty = Decimal(row.get("qty") or "0")
                unit_cost = Decimal(row.get("unit_cost") or "0")
                expiry = parse_date(row.get("expiry_date", ""))
                manufacturing = parse_date(row.get("manufacturing_date", ""))
            except (InvalidOperation, ValueError) as exc:
                report.error(index, f"invalid number/date: {exc}")
                continue
            if qty <= 0:
                report.error(index, "qty must be positive")
                continue
            if not medicine.no_batch and expiry is None:
                report.error(index, "expiry_date is required for this medicine")
                continue

            batch_number = row.get("batch_number") or "DEFAULT"
            existing_batch = MedicineBatch.objects.filter(
                branch=branch, medicine=medicine, batch_number=batch_number, expiry_date=expiry
            ).first()
            if existing_batch is None and dry_run:
                report.created += 1
                continue

            if existing_batch is not None:
                batch = existing_batch
            else:
                batch = MedicineBatch.objects.create(
                    branch=branch,
                    medicine=medicine,
                    batch_number=batch_number,
                    expiry_date=expiry,
                    manufacturing_date=manufacturing,
                    unit_cost=unit_cost,
                    status=BatchStatus.EXPIRED
                    if expiry and expiry < date.today()
                    else BatchStatus.ACTIVE,
                )
            key = f"import-opening-stock:{batch.id}"
            if InventoryTransaction.objects.filter(idempotency_key=key).exists():
                report.skipped += 1
                continue

            report.created += 1
            if dry_run:
                continue

            post_transactions(
                branch=branch,
                lines=[
                    MovementLine(
                        medicine=medicine,
                        batch=batch,
                        qty_delta=qty,
                        unit_cost=unit_cost,
                    )
                ],
                entry_type=EntryType.OPENING,
                source_type="OPENING_IMPORT",
                source_id=batch.id,
                source_number="OPENING",
                idempotency_key=key,
            )
            batch.qty_received_total = (batch.qty_received_total or Decimal("0")) + qty
            batch.save(update_fields=["qty_received_total", "updated_at"])

        report.finish(self, dry_run)
