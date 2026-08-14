"""Audit-log retention purge command."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_purge_audit_logs_keeps_recent_rows():
    old = AuditLog.objects.create(actor_type="SYSTEM", entity_type="x", action="old_action")
    AuditLog.objects.filter(id=old.id).update(
        created_at=timezone.now() - timedelta(days=400)
    )
    recent = AuditLog.objects.create(actor_type="SYSTEM", entity_type="x", action="new_action")

    call_command("purge_audit_logs", "--months", "6", verbosity=0)

    assert not AuditLog.objects.filter(id=old.id).exists()
    assert AuditLog.objects.filter(id=recent.id).exists()


def test_purge_audit_logs_dry_run():
    old = AuditLog.objects.create(actor_type="SYSTEM", entity_type="x", action="old")
    AuditLog.objects.filter(id=old.id).update(
        created_at=timezone.now() - timedelta(days=400)
    )

    call_command("purge_audit_logs", "--months", "6", "--dry-run", verbosity=0)

    assert AuditLog.objects.filter(id=old.id).exists()
