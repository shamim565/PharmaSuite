"""Shared helpers for CSV import commands."""

import csv
from pathlib import Path

from django.core.management.base import CommandError


def read_rows(path: str) -> list[dict]:
    file = Path(path)
    if not file.exists():
        raise CommandError(f"File not found: {file}")
    with file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise CommandError("CSV file has no header row.")
        return [{key.strip(): (value or "").strip() for key, value in row.items()} for row in reader]


class ImportReport:
    def __init__(self):
        self.created = 0
        self.skipped = 0
        self.errors: list[str] = []

    def error(self, line: int, message: str) -> None:
        self.errors.append(f"line {line}: {message}")

    def finish(self, command, dry_run: bool) -> None:
        from django.core.management.base import BaseCommand

        assert isinstance(command, BaseCommand)
        prefix = "[dry-run] " if dry_run else ""
        command.stdout.write(f"{prefix}created: {self.created}")
        command.stdout.write(f"{prefix}skipped (already exists): {self.skipped}")
        if self.errors:
            command.stdout.write(command.style.ERROR(f"errors: {len(self.errors)}"))
            for message in self.errors[:50]:
                command.stdout.write(command.style.ERROR(f"  {message}"))
        else:
            command.stdout.write(command.style.SUCCESS("no validation errors"))
