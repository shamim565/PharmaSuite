"""Create a PostgreSQL backup using pg_dump (custom format)."""

import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Create a PostgreSQL backup (pg_dump -Fc) for the configured database."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="backups", help="Output directory (default: backend/backups)")

    def handle(self, *args, **options):
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            raise CommandError("pg_dump not found on PATH. Install PostgreSQL client tools.")

        db = settings.DATABASES["default"]
        database = db.get("NAME")
        if not database:
            raise CommandError("DATABASE NAME is not configured.")

        output_dir = Path(options["output"])
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        target = output_dir / f"{database}-{stamp}.dump"

        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = db["PASSWORD"]

        command = [
            pg_dump,
            "-h", str(db.get("HOST") or "localhost"),
            "-p", str(db.get("PORT") or 5432),
            "-U", str(db.get("USER") or ""),
            "-Fc",
            "-f", str(target),
            str(database),
        ]
        subprocess.run(command, check=True, env=env)
        size = target.stat().st_size
        self.stdout.write(self.style.SUCCESS(f"Backup written: {target} ({size:,} bytes)"))
        self.stdout.write("Store an encrypted copy offsite (see docs/operations.md).")
