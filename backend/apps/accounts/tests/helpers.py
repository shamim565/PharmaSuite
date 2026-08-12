"""Helpers for building RBAC fixtures in tests."""

from uuid import uuid4

from apps.accounts.models import (
    BranchScope,
    Permission,
    PermissionEffect,
    Role,
    RolePermission,
    UserRole,
)


def make_permission(code, module="test", action="view", label=None):
    permission, _ = Permission.objects.get_or_create(
        code=code, defaults={"module": module, "action": action, "label": label or code}
    )
    return permission


def make_role(codes=(), *, branch_scope=BranchScope.ALL, prefix="T", module="test"):
    role = Role.objects.create(
        code=f"{prefix}{uuid4().hex[:8].upper()}",
        name="Test Role",
        branch_scope=branch_scope,
    )
    for code in codes:
        RolePermission.objects.create(
            role=role, permission=make_permission(code, module=module), effect=PermissionEffect.ALLOW
        )
    return role


def grant_role(user, codes, *, branch_scope=BranchScope.ALL, module="test"):
    role = make_role(codes, branch_scope=branch_scope, module=module)
    UserRole.objects.create(user=user, role=role)
    user._permission_cache = None
    return role
