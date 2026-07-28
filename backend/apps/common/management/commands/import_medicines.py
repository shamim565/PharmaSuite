"""Import medicines from CSV (master data for go-live migration)."""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Generic, Manufacturer, Medicine, Unit
from apps.common.management.commands._import_utils import ImportReport, read_rows


class Command(BaseCommand):
    help = "Import medicines from a CSV file (see docs/import-templates/medicines.csv)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["file"])
        dry_run = options["dry_run"]
        report = ImportReport()

        for index, row in enumerate(rows, start=2):
            code = row.get("code", "").upper()
            name = row.get("name", "")
            if not code or not name:
                report.error(index, "code and name are required")
                continue
            if Medicine.objects.filter(code=code).exists():
                report.skipped += 1
                continue
            try:
                payload = {
                    "purchase_price": Decimal(row.get("purchase_price") or "0"),
                    "selling_price": Decimal(row.get("selling_price") or "0"),
                    "mrp": Decimal(row.get("mrp") or "0"),
                    "vat_rate": Decimal(row.get("vat_rate") or "15"),
                    "reorder_level": Decimal(row.get("reorder_level") or "0"),
                }
            except InvalidOperation as exc:
                report.error(index, f"invalid number: {exc}")
                continue

            report.created += 1
            if dry_run:
                continue

            with transaction.atomic():
                generic = None
                if row.get("generic"):
                    generic, _ = Generic.objects.get_or_create(name=row["generic"])
                manufacturer = None
                if row.get("manufacturer"):
                    manufacturer, _ = Manufacturer.objects.get_or_create(name=row["manufacturer"])
                unit = None
                if row.get("base_unit"):
                    unit, _ = Unit.objects.get_or_create(name=row["base_unit"], defaults={"symbol": row["base_unit"][:20]})
                Medicine.objects.create(
                    code=code,
                    name=name,
                    generic=generic,
                    manufacturer=manufacturer,
                    base_unit=unit,
                    dosage_form=row.get("dosage_form", ""),
                    strength=row.get("strength", ""),
                    **payload,
                )

        report.finish(self, dry_run)
