from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.catalog.models import (
    BatchStatus,
    Generic,
    Manufacturer,
    Medicine,
    MedicineBatch,
    MedicineCategory,
    MedicineUnitConversion,
    Unit,
)
from apps.catalog.serializers import (
    GenericSerializer,
    ManufacturerSerializer,
    MedicineBatchSerializer,
    MedicineCategorySerializer,
    MedicineSerializer,
    MedicineUnitConversionSerializer,
    UnitSerializer,
)
from apps.common.exceptions import ConflictError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin


class AuditedMasterMixin:
    audit_entity = "Record"

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            actor=self.request.user,
            action=f"{self.audit_entity.lower()}_created",
            entity_type=self.audit_entity,
            entity_id=instance.id,
            after=serializer.data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = self.get_serializer(self.get_object()).data
        instance = serializer.save()
        log_action(
            actor=self.request.user,
            action=f"{self.audit_entity.lower()}_updated",
            entity_type=self.audit_entity,
            entity_id=instance.id,
            before=before,
            after=self.get_serializer(instance).data,
            request=self.request,
        )


class GenericViewSet(
    AuditedMasterMixin,
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    audit_entity = "Generic"
    permission_map = {
        "list": ["MEDICINE_VIEW"],
        "retrieve": ["MEDICINE_VIEW"],
        "create": ["MEDICINE_MANAGE"],
        "update": ["MEDICINE_MANAGE"],
        "partial_update": ["MEDICINE_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = GenericSerializer
    queryset = Generic.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["name", "therapeutic_class"]
    ordering = ["name"]


class ManufacturerViewSet(GenericViewSet):
    audit_entity = "Manufacturer"
    serializer_class = ManufacturerSerializer
    queryset = Manufacturer.objects.all()
    search_fields = ["name", "country"]


class MedicineCategoryViewSet(GenericViewSet):
    audit_entity = "MedicineCategory"
    serializer_class = MedicineCategorySerializer
    queryset = MedicineCategory.objects.select_related("parent")
    filterset_fields = ["is_active", "parent"]
    search_fields = ["name"]


class UnitViewSet(GenericViewSet):
    audit_entity = "Unit"
    serializer_class = UnitSerializer
    queryset = Unit.objects.all()
    filterset_fields = ["is_active", "unit_type"]
    search_fields = ["name", "symbol"]


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
        "conversions": ["MEDICINE_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = MedicineSerializer
    queryset = Medicine.objects.select_related(
        "generic", "manufacturer", "category", "base_unit"
    ).prefetch_related("barcodes", "conversions__unit")
    filterset_fields = [
        "is_active",
        "category",
        "manufacturer",
        "generic",
        "dosage_form",
        "no_batch",
        "rx_required",
        "cold_chain",
    ]
    search_fields = ["code", "name", "generic__name", "manufacturer__name", "barcodes__barcode"]
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

    @action(detail=True, methods=["get", "post"], url_path="conversions")
    def conversions(self, request, pk=None):
        medicine = self.get_object()
        if request.method == "GET":
            rows = medicine.conversions.select_related("unit").all()
            return Response(MedicineUnitConversionSerializer(rows, many=True).data)

        serializer = MedicineUnitConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = serializer.validated_data["unit"]
        if medicine.conversions.filter(unit=unit).exists():
            raise ConflictError("CONVERSION_EXISTS", "This unit conversion already exists.")
        conversion = serializer.save(medicine=medicine)
        log_action(
            actor=request.user,
            action="conversion_added",
            entity_type="MedicineUnitConversion",
            entity_id=conversion.id,
            after=MedicineUnitConversionSerializer(conversion).data,
            request=request,
        )
        return Response(
            MedicineUnitConversionSerializer(conversion).data, status=status.HTTP_201_CREATED
        )


class MedicineUnitConversionViewSet(
    PermissionMappedMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "retrieve": ["MEDICINE_VIEW"],
        "update": ["MEDICINE_MANAGE"],
        "partial_update": ["MEDICINE_MANAGE"],
        "destroy": ["MEDICINE_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = MedicineUnitConversionSerializer
    queryset = MedicineUnitConversion.objects.select_related("medicine", "unit")


class MedicineBatchViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["STOCK_VIEW"],
        "retrieve": ["STOCK_VIEW"],
        "create": ["STOCK_ADJUST"],
        "update": ["STOCK_ADJUST"],
        "partial_update": ["STOCK_ADJUST"],
    }
    permission_classes = [HasPermission]
    serializer_class = MedicineBatchSerializer
    queryset = MedicineBatch.objects.select_related("branch", "medicine")
    filterset_fields = ["branch", "medicine", "status", "batch_number"]
    search_fields = ["batch_number", "medicine__name", "medicine__code"]
    ordering_fields = ["expiry_date", "created_at", "batch_number"]
    ordering = ["expiry_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return qs
        return qs.filter(branch_id__in=user.branch_ids)

    def perform_create(self, serializer):
        batch = serializer.save()
        if (
            batch.expiry_date
            and batch.expiry_date < timezone.localdate()
            and batch.status == BatchStatus.ACTIVE
        ):
            batch.status = BatchStatus.EXPIRED
            batch.save(update_fields=["status", "updated_at"])
        log_action(
            actor=self.request.user,
            action="batch_created",
            entity_type="MedicineBatch",
            entity_id=batch.id,
            after=MedicineBatchSerializer(batch).data,
            branch=batch.branch,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = MedicineBatchSerializer(self.get_object()).data
        batch = serializer.save()
        log_action(
            actor=self.request.user,
            action="batch_updated",
            entity_type="MedicineBatch",
            entity_id=batch.id,
            before=before,
            after=MedicineBatchSerializer(batch).data,
            branch=batch.branch,
            request=self.request,
        )
