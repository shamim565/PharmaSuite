class PermissionMappedMixin:
    """Maps DRF view actions to required permission codes for HasPermission."""

    permission_map: dict[str, list[str]] = {}

    @property
    def required_permissions(self) -> list[str]:
        action = getattr(self, "action", None)
        if action is None:
            return []
        return self.permission_map.get(action, [])
