"""seed_rbac must not silently overwrite UI/API role edits."""

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.accounts.services import replace_role_permissions

pytestmark = pytest.mark.django_db


def _codes(role):
    return set(role.role_permissions.values_list("permission__code", flat=True))


def test_seed_preserves_role_edits_until_forced():
    call_command("seed_rbac", verbosity=0)
    owner = User.objects.get(mobile="01700000000")
    assert owner.is_superuser

    role = Role.objects.get(code="OWNER")
    original = _codes(role)
    assert len(original) > 40

    replace_role_permissions(actor=owner, role=role, permissions=[{"code": "USER_VIEW"}])
    assert _codes(role) == {"USER_VIEW"}

    call_command("seed_rbac", verbosity=0)
    assert _codes(role) == {"USER_VIEW"}, "seed without --sync-permissions must keep edits"

    call_command("seed_rbac", "--sync-permissions", verbosity=0)
    assert _codes(role) == original


def test_seed_is_idempotent_for_permission_catalog():
    call_command("seed_rbac", verbosity=0)
    from apps.accounts.models import Permission

    count = Permission.objects.count()
    call_command("seed_rbac", verbosity=0)
    assert Permission.objects.count() == count
