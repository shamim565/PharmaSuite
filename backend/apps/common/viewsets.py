UNMAPPED_ACTION = "__UNMAPPED_ACTION__"


class PermissionMappedMixin:
    """Maps DRF view actions to required permission codes for HasPermission.

    Unmapped actions fail closed: they resolve to a permission code that can
    never be granted. An action that is intentionally open to any authenticated
    user must be mapped explicitly to an empty list.
    """

    permission_map: dict[str, list[str]] = {}

    @property
    def required_permissions(self) -> list[str]:
        action = getattr(self, "action", None)
        if action is None:
            # Non-action requests (e.g. OPTIONS metadata) are not permission-mapped.
            return []
        if action not in self.permission_map:
            return [UNMAPPED_ACTION]
        return self.permission_map[action]
