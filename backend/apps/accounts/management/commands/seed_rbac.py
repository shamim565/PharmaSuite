import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import (
    BranchScope,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
    UserStatus,
)
from apps.accounts.rbac import PERMISSION_CATALOG, ROLE_DEFINITIONS, role_permission_codes
from apps.branches.models import Branch, BranchType


class Command(BaseCommand):
    help = "Seed the RBAC permission catalog, system roles, main branch, and owner user."

    def handle(self, *args, **options):
        permissions_created = 0
        roles_synced = 0

        with transaction.atomic():
            for code, module, action, label, sensitive in PERMISSION_CATALOG:
                _, created = Permission.objects.update_or_create(
                    code=code,
                    defaults={
                        "module": module,
                        "action": action,
                        "label": label,
                        "is_sensitive": sensitive,
                    },
                )
                permissions_created += int(created)

            for role_code, definition in ROLE_DEFINITIONS.items():
                role, _ = Role.objects.update_or_create(
                    code=role_code,
                    defaults={
                        "name": definition["name"],
                        "description": definition.get("description", ""),
                        "is_system": True,
                        "branch_scope": definition.get("scope", BranchScope.ASSIGNED),
                    },
                )
                codes = role_permission_codes(definition)
                permission_map = {p.code: p for p in Permission.objects.filter(code__in=codes)}
                RolePermission.objects.filter(role=role).exclude(
                    permission__code__in=codes
                ).delete()
                existing = set(role.role_permissions.values_list("permission__code", flat=True))
                RolePermission.objects.bulk_create(
                    [
                        RolePermission(role=role, permission=permission_map[code])
                        for code in sorted(codes)
                        if code not in existing
                    ],
                    ignore_conflicts=True,
                )
                roles_synced += 1

            branch, branch_created = Branch.objects.get_or_create(
                code="MAIN",
                defaults={
                    "name": "Main Branch",
                    "type": BranchType.HEAD_OFFICE,
                    "invoice_prefix": "MAIN",
                },
            )

            owner_mobile = os.environ.get("OWNER_MOBILE", "01700000000")
            owner_password = os.environ.get("OWNER_PASSWORD", "Admin@1234")
            owner, owner_created = User.objects.get_or_create(
                mobile=owner_mobile,
                defaults={
                    "full_name": "Owner",
                    "is_superuser": True,
                    "status": UserStatus.ACTIVE,
                },
            )
            if owner_created:
                owner.set_password(owner_password)
                owner.save(update_fields=["password"])
            owner.default_branch = branch
            owner.save(update_fields=["default_branch", "updated_at"])

            UserRole.objects.get_or_create(user=owner, role=Role.objects.get(code="OWNER"))
            UserBranch.objects.get_or_create(
                user=owner, branch=branch, defaults={"is_default": True}
            )

            from apps.accounting.models import AccountType, FinancialAccount
            from apps.branches.models import Branch as BranchModel

            cash_accounts = 0
            for branch_row in BranchModel.objects.all():
                _, created = FinancialAccount.objects.get_or_create(
                    code=f"{branch_row.code}-CASH",
                    defaults={
                        "name": f"{branch_row.name} Cash",
                        "account_type": AccountType.CASH,
                        "branch": branch_row,
                        "allow_negative": False,
                    },
                )
                cash_accounts += int(created)

        self.stdout.write(self.style.SUCCESS("RBAC seed complete"))
        self.stdout.write(f"  permissions created: {permissions_created}")
        self.stdout.write(f"  roles synced: {roles_synced}")
        self.stdout.write(f"  default cash accounts created: {cash_accounts}")
        self.stdout.write(f"  branch: {branch.code} ({'created' if branch_created else 'existing'})")
        if owner_created:
            self.stdout.write(
                self.style.WARNING(
                    f"  owner created: mobile={owner_mobile} password={owner_password} (change immediately)"
                )
            )
        else:
            self.stdout.write(f"  owner exists: mobile={owner_mobile}")
