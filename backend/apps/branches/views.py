from rest_framework import mixins, viewsets

from apps.branches.models import Branch
from apps.branches.serializers import BranchSerializer
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin


class BranchViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["BRANCH_VIEW"],
        "retrieve": ["BRANCH_VIEW"],
        "create": ["BRANCH_MANAGE"],
        "update": ["BRANCH_MANAGE"],
        "partial_update": ["BRANCH_MANAGE"],
        "mine": ["BRANCH_VIEW"],
    }
    permission_classes = [HasPermission]
    serializer_class = BranchSerializer
    queryset = Branch.objects.all().select_related("manager")
    filterset_fields = ["type", "status"]
    search_fields = ["code", "name", "phone"]
    ordering = ["name"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return super().get_queryset()
        return super().get_queryset().filter(id__in=user.branch_ids)

    @property
    def required_permissions(self) -> list[str]:
        if getattr(self, "action", None) == "mine":
            return []
        return self.permission_map.get(getattr(self, "action", ""), [])
