from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import log_action
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.sales.delivery_models import DeliveryChallan
from apps.sales.delivery_serializers import (
    DeliveryChallanCancelSerializer,
    DeliveryChallanCompleteSerializer,
    DeliveryChallanCreateSerializer,
    DeliveryChallanFromInvoiceSerializer,
    DeliveryChallanReadSerializer,
)
from apps.sales.delivery_services import (
    cancel_delivery_challan,
    complete_delivery_challan,
    create_challan_from_invoice,
    create_delivery_challan,
    dispatch_delivery_challan,
    mark_undelivered_challan,
)
from apps.sales.views import scoped_sales


class DeliveryChallanViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["SALE_VIEW"],
        "retrieve": ["SALE_VIEW"],
        "create": ["SALE_CONFIRM"],
        "from_invoice": ["SALE_CONFIRM"],
        "dispatch_challan": ["SALE_CONFIRM"],
        "deliver": ["SALE_CONFIRM"],
        "undeliver": ["SALE_CONFIRM"],
        "cancel": ["SALE_CONFIRM"],
    }
    permission_classes = [HasPermission]
    queryset = (
        DeliveryChallan.objects.select_related(
            "customer", "branch", "invoice", "dispatched_by", "delivered_by"
        ).prefetch_related("items__medicine", "items__batch")
    )
    filterset_fields = ["status", "customer", "branch", "business_date", "invoice"]
    search_fields = ["number", "customer__name", "delivery_person", "vehicle_no"]
    ordering_fields = ["business_date", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        return scoped_sales(self.request.user, super().get_queryset())

    def get_serializer_class(self):
        if self.action == "create":
            return DeliveryChallanCreateSerializer
        return DeliveryChallanReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = DeliveryChallanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        challan = create_delivery_challan(
            branch=data["branch"],
            customer=data["customer"],
            invoice=data.get("invoice"),
            business_date=data["business_date"],
            delivery_person=data.get("delivery_person", ""),
            delivery_phone=data.get("delivery_phone", ""),
            vehicle_no=data.get("vehicle_no", ""),
            notes=data.get("notes", ""),
            items=data["items"],
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_CREATED",
            entity_type="delivery_challan",
            entity_id=challan.id,
            after={"number": challan.number, "status": challan.status},
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="from-invoice")
    def from_invoice(self, request):
        serializer = DeliveryChallanFromInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        challan = create_challan_from_invoice(
            invoice=data["invoice"],
            delivery_person=data.get("delivery_person", ""),
            delivery_phone=data.get("delivery_phone", ""),
            vehicle_no=data.get("vehicle_no", ""),
            notes=data.get("notes", ""),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_CREATED_FROM_INVOICE",
            entity_type="delivery_challan",
            entity_id=challan.id,
            after={"number": challan.number, "invoice_id": str(data["invoice"].id)},
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_challan(self, request, pk=None):
        challan = self.get_object()
        challan = dispatch_delivery_challan(challan=challan, actor=request.user)
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_DISPATCHED",
            entity_type="delivery_challan",
            entity_id=challan.id,
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data)

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        challan = self.get_object()
        serializer = DeliveryChallanCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        challan = complete_delivery_challan(
            challan=challan,
            actor=request.user,
            recipient_name=data.get("recipient_name", ""),
            recipient_phone=data.get("recipient_phone", ""),
            notes=data.get("notes", ""),
        )
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_DELIVERED",
            entity_type="delivery_challan",
            entity_id=challan.id,
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data)

    @action(detail=True, methods=["post"])
    def undeliver(self, request, pk=None):
        challan = self.get_object()
        serializer = DeliveryChallanCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challan = mark_undelivered_challan(
            challan=challan, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_UNDELIVERED",
            entity_type="delivery_challan",
            entity_id=challan.id,
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        challan = self.get_object()
        serializer = DeliveryChallanCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challan = cancel_delivery_challan(
            challan=challan, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        log_action(
            actor=request.user,
            action="DELIVERY_CHALLAN_CANCELLED",
            entity_type="delivery_challan",
            entity_id=challan.id,
            request=request,
        )
        return Response(DeliveryChallanReadSerializer(challan).data)
