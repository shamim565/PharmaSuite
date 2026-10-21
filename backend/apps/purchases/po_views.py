from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.purchases.po_models import PurchaseOrder
from apps.purchases.po_serializers import (
    PurchaseOrderCancelSerializer,
    PurchaseOrderConvertSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderReadSerializer,
)
from apps.purchases.po_services import (
    approve_purchase_order,
    cancel_purchase_order,
    convert_po_to_purchase,
    create_purchase_order,
    submit_purchase_order,
)
from apps.purchases.serializers import PurchaseReadSerializer
from apps.purchases.views import scoped_purchases


class PurchaseOrderViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["PURCHASE_VIEW"],
        "retrieve": ["PURCHASE_VIEW"],
        "create": ["PURCHASE_MANAGE"],
        "submit": ["PURCHASE_MANAGE"],
        "approve": ["PURCHASE_CONFIRM"],
        "cancel": ["PURCHASE_CONFIRM"],
        "convert_to_purchase": ["PURCHASE_CONFIRM"],
    }
    permission_classes = [HasPermission]
    queryset = (
        PurchaseOrder.objects.select_related(
            "supplier", "branch", "submitted_by", "approved_by", "cancelled_by", "fulfilled_by"
        ).prefetch_related("items__medicine")
    )
    filterset_fields = ["status", "supplier", "branch", "business_date"]
    search_fields = ["number", "supplier__name", "notes"]
    ordering_fields = ["business_date", "grand_total", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        return scoped_purchases(self.request.user, super().get_queryset())

    def get_serializer_class(self):
        if self.action == "create":
            return PurchaseOrderCreateSerializer
        return PurchaseOrderReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = PurchaseOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        po = create_purchase_order(
            branch=data["branch"],
            supplier=data["supplier"],
            business_date=data["business_date"],
            expected_delivery_date=data.get("expected_delivery_date"),
            items=data["items"],
            notes=data.get("notes", ""),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PURCHASE_ORDER_CREATED",
            entity_type="purchase_order",
            entity_id=po.id,
            after={"number": po.number, "status": po.status, "grand_total": str(po.grand_total)},
            request=request,
        )
        return Response(PurchaseOrderReadSerializer(po).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        po = self.get_object()
        po = submit_purchase_order(purchase_order=po, actor=request.user)
        log_action(
            actor=request.user,
            action="PURCHASE_ORDER_SUBMITTED",
            entity_type="purchase_order",
            entity_id=po.id,
            request=request,
        )
        return Response(PurchaseOrderReadSerializer(po).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        po = self.get_object()
        po = approve_purchase_order(purchase_order=po, actor=request.user)
        log_action(
            actor=request.user,
            action="PURCHASE_ORDER_APPROVED",
            entity_type="purchase_order",
            entity_id=po.id,
            after={"number": po.number, "status": po.status},
            request=request,
        )
        return Response(PurchaseOrderReadSerializer(po).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        po = cancel_purchase_order(
            purchase_order=po, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        log_action(
            actor=request.user,
            action="PURCHASE_ORDER_CANCELLED",
            entity_type="purchase_order",
            entity_id=po.id,
            after={"status": po.status, "reason": po.cancel_reason},
            request=request,
        )
        return Response(PurchaseOrderReadSerializer(po).data)

    @action(detail=True, methods=["post"], url_path="convert-to-purchase")
    def convert_to_purchase(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = convert_po_to_purchase(
            purchase_order=po,
            actor=request.user,
            supplier_invoice_number=serializer.validated_data["supplier_invoice_number"],
            supplier_invoice_date=serializer.validated_data.get("supplier_invoice_date"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PURCHASE_ORDER_CONVERTED",
            entity_type="purchase_order",
            entity_id=po.id,
            after={"purchase_id": str(purchase.id), "status": po.status},
            request=request,
        )
        return Response(
            {
                "purchase_order": PurchaseOrderReadSerializer(po).data,
                "purchase": PurchaseReadSerializer(purchase).data,
            },
            status=status.HTTP_201_CREATED,
        )
