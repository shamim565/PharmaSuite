from rest_framework import mixins, viewsets

from apps.audit.services import log_action
from apps.catalog.models import Medicine
from apps.catalog.serializers import MedicineSerializer
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin


class MedicineViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["MEDICINE_VIEW"],
        "retrieve": ["MEDICINE_VIEW"],
        "create": ["MEDICINE_MANAGE"],
        "update": ["MEDICINE_MANAGE"],
        "partial_update": ["MEDICINE_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = MedicineSerializer
    queryset = Medicine.objects.all()
    filterset_fields = ["is_active", "category", "manufacturer", "dosage_form"]
    search_fields = ["code", "name", "generic_name", "manufacturer"]
    ordering_fields = ["name", "code", "created_at", "selling_price"]
    ordering = ["name"]

    def perform_create(self, serializer):
        medicine = serializer.save()
        log_action(
            actor=self.request.user,
            action="medicine_created",
            entity_type="Medicine",
            entity_id=medicine.id,
            after=MedicineSerializer(medicine).data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = MedicineSerializer(self.get_object()).data
        medicine = serializer.save()
        log_action(
            actor=self.request.user,
            action="medicine_updated",
            entity_type="Medicine",
            entity_id=medicine.id,
            before=before,
            after=MedicineSerializer(medicine).data,
            request=self.request,
        )
