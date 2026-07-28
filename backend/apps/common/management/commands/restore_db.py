"""Restore a PostgreSQL backup created by backup_db (destructive)."""

import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restore a pg_dump custom-format backup into the configured database."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the .dump file")
        parser.add_argument("--confirm", action="store_true", help="Required acknowledgement of destructive restore")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Restore is destructive. Re-run with --confirm.")
        pg_restore = shutil.which("pg_restore")
        if not pg_restore:
            raise CommandError("pg_restore not found on PATH.")

        dump = Path(options["file"])
        if not dump.exists():
            raise CommandError(f"Backup file not found: {dump}")

        db = settings.DATABASES["default"]
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = db["PASSWORD"]

        command = [
            pg_restore,
            "--clean",
            "--if-exists",
            "-h", str(db.get("HOST") or "localhost"),
            "-p", str(db.get("PORT") or 5432),
            "-U", str(db.get("USER") or ""),
            "-d", str(db.get("NAME")),
            str(dump),
        ]
        subprocess.run(command, check=True, env=env)
        self.stdout.write(self.style.SUCCESS(f"Restore complete from {dump}."))
        self.stdout.write("Run manage.py check_ledger_integrity and check_stock_integrity to verify.")
