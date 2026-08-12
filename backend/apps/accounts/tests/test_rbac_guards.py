"""Tests for privilege-escalation guards in role/user management."""

import pytest

from apps.accounts.models import (
    BranchScope,
    PermissionEffect,
    RolePermission,
    UserBranch,
)
from apps.accounts.services import (
    create_role,
    create_user,
    replace_role_permissions,
    set_user_status,
    update_role,
    update_user,
)
from apps.accounts.tests.helpers import grant_role, make_permission, make_role
from apps.common.exceptions import APIError
from apps.common.viewsets import UNMAPPED_ACTION, PermissionMappedMixin

pytestmark = pytest.mark.django_db


def test_grant_guard_blocks_unheld_permission(actor):
    grant_role(actor, ["ROLE_MANAGE", "ROLE_VIEW"])
    role = make_role()

    with pytest.raises(APIError) as exc:
        replace_role_permissions(
            actor=actor, role=role, permissions=[{"code": "PERIOD_OVERRIDE"}]
        )
    assert exc.value.code == "PRIVILEGE_ESCALATION"
    assert exc.value.status_code == 403
    assert role.role_permissions.count() == 0


def test_grant_guard_allows_held_permission(actor):
    grant_role(actor, ["ROLE_MANAGE", "ROLE_VIEW"])
    role = make_role()

    replace_role_permissions(
        actor=actor, role=role, permissions=[{"code": "ROLE_VIEW", "effect": "ALLOW"}]
    )
    assert set(role.role_permissions.values_list("permission__code", flat=True)) == {
        "ROLE_VIEW"
    }


def test_deny_effect_is_allowed_and_reduces_access(actor):
    grant_role(actor, ["ROLE_MANAGE"])
    make_permission("USER_VIEW")
    role = make_role()
    replace_role_permissions(
        actor=actor, role=role, permissions=[{"code": "USER_VIEW", "effect": "DENY"}]
    )
    assert set(role.role_permissions.values_list("permission__code", flat=True)) == {
        "USER_VIEW"
    }


def test_superuser_can_grant_anything(actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    make_permission("PERIOD_OVERRIDE")
    role = make_role()

    replace_role_permissions(
        actor=actor, role=role, permissions=[{"code": "PERIOD_OVERRIDE"}]
    )
    assert set(role.role_permissions.values_list("permission__code", flat=True)) == {
        "PERIOD_OVERRIDE"
    }


def test_cannot_edit_role_more_privileged_than_actor(actor):
    grant_role(actor, ["ROLE_MANAGE"])
    role = make_role(["PERIOD_OVERRIDE"])

    with pytest.raises(APIError) as exc:
        replace_role_permissions(actor=actor, role=role, permissions=[])
    assert exc.value.code == "ROLE_MORE_PRIVILEGED"

    with pytest.raises(APIError) as exc:
        update_role(actor=actor, role=role, data={"name": "Renamed"})
    assert exc.value.code == "ROLE_MORE_PRIVILEGED"


def test_cannot_assign_role_with_unheld_permissions(actor, approver):
    grant_role(actor, ["USER_MANAGE"])
    privileged = make_role(["USER_MANAGE", "PERIOD_OVERRIDE"])

    with pytest.raises(APIError) as exc:
        update_user(actor=actor, user=approver, data={"role_ids": [privileged.id]})
    assert exc.value.code == "PRIVILEGE_ESCALATION"
    assert not approver.user_roles.exists()


def test_can_assign_role_within_actor_permissions(actor, approver):
    grant_role(actor, ["USER_MANAGE"])
    allowed = make_role(["USER_MANAGE"])

    update_user(actor=actor, user=approver, data={"role_ids": [allowed.id]})
    assert approver.user_roles.filter(role=allowed).exists()


def test_cannot_manage_more_privileged_user(actor, approver):
    grant_role(actor, ["USER_MANAGE"])
    grant_role(approver, ["PERIOD_OVERRIDE"])

    with pytest.raises(APIError) as exc:
        set_user_status(actor=actor, user=approver, active=False)
    assert exc.value.code == "TARGET_MORE_PRIVILEGED"

    with pytest.raises(APIError) as exc:
        update_user(actor=actor, user=approver, data={"full_name": "Hacked"})
    assert exc.value.code == "TARGET_MORE_PRIVILEGED"


def test_cannot_manage_superuser(actor, approver):
    grant_role(actor, ["USER_MANAGE"])
    approver.is_superuser = True
    approver.save(update_fields=["is_superuser"])

    with pytest.raises(APIError) as exc:
        set_user_status(actor=actor, user=approver, active=False)
    assert exc.value.code == "TARGET_MORE_PRIVILEGED"


def test_all_branch_role_requires_all_branch_actor(actor):
    grant_role(actor, ["ROLE_MANAGE"], branch_scope=BranchScope.ASSIGNED)

    with pytest.raises(APIError) as exc:
        create_role(
            actor=actor,
            data={"code": "GLOBAL_ROLE", "name": "Global", "branch_scope": "ALL"},
        )
    assert exc.value.code == "PRIVILEGE_ESCALATION"


def test_branch_assignment_cannot_exceed_actor_scope(actor, branch, second_branch):
    grant_role(actor, ["USER_MANAGE"], branch_scope=BranchScope.ASSIGNED)
    UserBranch.objects.create(user=actor, branch=branch)
    actor._permission_cache = None

    with pytest.raises(APIError) as exc:
        create_user(
            actor=actor,
            data={
                "full_name": "New User",
                "mobile": "01711111111",
                "password": "Xyz@12345",
                "branch_ids": [second_branch.id],
            },
        )
    assert exc.value.code == "BRANCH_SCOPE_EXCEEDED"
    assert not actor.__class__.objects.filter(mobile="01711111111").exists()


def test_branch_assignment_allows_own_scope(actor, branch):
    grant_role(actor, ["USER_MANAGE"], branch_scope=BranchScope.ASSIGNED)
    UserBranch.objects.create(user=actor, branch=branch)
    actor._permission_cache = None

    created = create_user(
        actor=actor,
        data={
            "full_name": "New User",
            "mobile": "01711111112",
            "password": "Xyz@12345",
            "branch_ids": [branch.id],
            "default_branch_id": branch.id,
        },
    )
    assert created.user_branches.filter(branch=branch).exists()


def test_deny_overrides_allow(actor):
    role = make_role()
    RolePermission.objects.create(
        role=role,
        permission=make_permission("USER_VIEW"),
        effect=PermissionEffect.DENY,
    )
    from apps.accounts.models import UserRole

    UserRole.objects.create(user=actor, role=role)
    actor._permission_cache = None

    assert "USER_VIEW" not in actor.effective_permission_codes


def test_unmapped_action_fails_closed():
    class DummyView(PermissionMappedMixin):
        permission_map = {"list": ["USER_VIEW"]}
        action = "mystery"

    assert DummyView().required_permissions == [UNMAPPED_ACTION]
