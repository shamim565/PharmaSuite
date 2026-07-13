from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """View-level permission check against the RBAC permission catalog.

    Views declare ``required_permissions = ["USER_MANAGE", ...]``.
    Superusers bypass; all others are checked against their effective permissions.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        required = getattr(view, "required_permissions", None) or []
        if not required:
            return True
        return all(code in user.effective_permission_codes for code in required)


def filter_by_branch_scope(queryset, user, field: str = "branch_id"):
    """Restrict a queryset to the user's assigned branches unless they have all-branch scope."""
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(**{f"{field}__in": user.branch_ids})
