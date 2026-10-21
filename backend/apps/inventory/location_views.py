from rest_framework import mixins, viewsets

from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.inventory.location_serializers import WarehouseLocationSerializer
from apps.inventory.models import WarehouseLocation


class WarehouseLocationViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Physical bin/rack locations in branch warehouses.

    Read requires STOCK_VIEW; write requires STOCK_ADJUST (warehouse control).
    """

    permission_map = {
        "list": ["STOCK_VIEW"],
        "retrieve": ["STOCK_VIEW"],
        "create": ["STOCK_ADJUST"],
        "update": ["STOCK_ADJUST"],
        "partial_update": ["STOCK_ADJUST"],
        "destroy": ["STOCK_ADJUST"],
    }
    permission_classes = [HasPermission]
    serializer_class = WarehouseLocationSerializer
    queryset = WarehouseLocation.objects.select_related("branch")
    filterset_fields = ["branch", "is_active"]
    search_fields = ["zone", "rack", "bin", "notes"]
    ordering_fields = ["branch", "zone", "rack", "bin"]
    ordering = ["zone", "rack", "bin"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return qs
        return qs.filter(branch_id__in=user.branch_ids)
