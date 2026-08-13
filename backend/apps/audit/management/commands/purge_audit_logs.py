"""Delete audit-log rows older than the retention window."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Purge audit log entries older than the configured retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=None,
            help="Retention window in months (overrides AUDIT_RETENTION_MONTHS).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        months = options["months"] or settings.AUDIT_RETENTION_MONTHS
        if months <= 0:
            self.stdout.write(self.style.WARNING("Retention must be a positive month count."))
            return

        cutoff = timezone.now() - timedelta(days=30 * months)
        queryset = AuditLog.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Dry run: {count} audit row(s) older than {cutoff.date()} would be deleted."
            )
            return

        queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {count} audit row(s) older than {cutoff.date()} ({months} months)."
            )
        )
