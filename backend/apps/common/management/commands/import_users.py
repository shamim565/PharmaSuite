"""Import users from CSV with roles and branches (go-live migration)."""

from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.accounts.services import create_user
from apps.branches.models import Branch
from apps.common.management.commands._import_utils import ImportReport, read_rows


class Command(BaseCommand):
    help = "Import users from CSV (see docs/import-templates/users.csv)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["file"])
        dry_run = options["dry_run"]
        report = ImportReport()

        for index, row in enumerate(rows, start=2):
            mobile = row.get("mobile", "")
            full_name = row.get("full_name", "")
            password = row.get("password", "")
            if not mobile or not full_name or len(password) < 8:
                report.error(index, "full_name, mobile and password (min 8 chars) are required")
                continue
            if User.objects.filter(mobile=mobile).exists():
                report.skipped += 1
                continue

            role = Role.objects.filter(code=row.get("role_code", "").upper()).first()
            branch = Branch.objects.filter(code=row.get("branch_code", "").upper()).first()
            if row.get("role_code") and role is None:
                report.error(index, f"role not found: {row['role_code']}")
                continue
            if row.get("branch_code") and branch is None:
                report.error(index, f"branch not found: {row['branch_code']}")
                continue

            report.created += 1
            if dry_run:
                continue

            create_user(
                actor=None,
                data={
                    "full_name": full_name,
                    "mobile": mobile,
                    "email": row.get("email") or None,
                    "password": password,
                    "role_ids": [role.id] if role else [],
                    "branch_ids": [branch.id] if branch else [],
                    "default_branch_id": branch.id if branch else None,
                },
            )

        report.finish(self, dry_run)
