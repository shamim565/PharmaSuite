from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.purchases.credit_models import SupplierCreditNote
from apps.purchases.credit_serializers import (
    SupplierCreditNoteCancelSerializer,
    SupplierCreditNoteCreateSerializer,
    SupplierCreditNoteReadSerializer,
)
from apps.purchases.credit_services import (
    cancel_supplier_credit_note,
    create_supplier_credit_note,
    settle_supplier_credit_note,
)
from apps.purchases.views import scoped_purchases


class SupplierCreditNoteViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Supplier credit notes (e.g. for returned expired goods)."""

    permission_map = {
        "list": ["SUPPLIER_VIEW"],
        "retrieve": ["SUPPLIER_VIEW"],
        "create": ["PURCHASE_CONFIRM"],
        "settle": ["PURCHASE_CONFIRM"],
        "cancel": ["PURCHASE_CONFIRM"],
    }
    permission_classes = [HasPermission]
    queryset = SupplierCreditNote.objects.select_related(
        "branch", "supplier", "settled_by", "adjustment"
    )
    filterset_fields = ["status", "supplier", "branch", "business_date", "reason_code"]
    search_fields = ["number", "supplier__name", "reference", "notes"]
    ordering_fields = ["business_date", "amount", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        return scoped_purchases(self.request.user, super().get_queryset())

    def get_serializer_class(self):
        if self.action == "create":
            return SupplierCreditNoteCreateSerializer
        return SupplierCreditNoteReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = SupplierCreditNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        note = create_supplier_credit_note(
            branch=data["branch"],
            supplier=data["supplier"],
            business_date=data["business_date"],
            amount=data["amount"],
            reason_code=data["reason_code"],
            reference=data.get("reference", ""),
            notes=data.get("notes", ""),
            adjustment=data.get("adjustment"),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SUPPLIER_CREDIT_NOTE_CREATED",
            entity_type="supplier_credit_note",
            entity_id=note.id,
            after={"number": note.number, "amount": str(note.amount), "status": note.status},
            request=request,
        )
        return Response(SupplierCreditNoteReadSerializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        note = self.get_object()
        note = settle_supplier_credit_note(credit_note=note, actor=request.user)
        log_action(
            actor=request.user,
            action="SUPPLIER_CREDIT_NOTE_SETTLED",
            entity_type="supplier_credit_note",
            entity_id=note.id,
            after={"number": note.number, "status": note.status},
            request=request,
        )
        return Response(SupplierCreditNoteReadSerializer(note).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        note = self.get_object()
        serializer = SupplierCreditNoteCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = cancel_supplier_credit_note(
            credit_note=note,
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        log_action(
            actor=request.user,
            action="SUPPLIER_CREDIT_NOTE_CANCELLED",
            entity_type="supplier_credit_note",
            entity_id=note.id,
            after={"number": note.number, "status": note.status},
            request=request,
        )
        return Response(SupplierCreditNoteReadSerializer(note).data)
