from datetime import timedelta
from decimal import Decimal

import django_filters
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.audit.services import log_action
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.purchases.models import (
    Purchase,
    PurchaseReturn,
    PurchaseStatus,
    SupplierPayment,
)
from apps.purchases.serializers import (
    PurchaseReadSerializer,
    PurchaseReturnCreateSerializer,
    PurchaseReturnReadSerializer,
    PurchaseWriteSerializer,
    SupplierPaymentCreateSerializer,
    SupplierPaymentReadSerializer,
)
from apps.purchases.services import (
    cancel_purchase,
    confirm_purchase,
    confirm_purchase_return,
    record_supplier_payment,
    reverse_supplier_payment,
)
from apps.suppliers.models import Supplier


def scoped_purchases(user, queryset):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(branch_id__in=user.branch_ids)


class SupplierPaymentFilter(django_filters.FilterSet):
    """Allows filtering payments by the purchase they are allocated to."""

    purchase = django_filters.UUIDFilter(field_name="allocations__purchase")

    class Meta:
        model = SupplierPayment
        fields = ["supplier", "branch", "status", "method", "purchase"]


class PurchaseViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["PURCHASE_VIEW"],
        "retrieve": ["PURCHASE_VIEW"],
        "create": ["PURCHASE_MANAGE"],
        "update": ["PURCHASE_MANAGE"],
        "partial_update": ["PURCHASE_MANAGE"],
        "confirm": ["PURCHASE_CONFIRM"],
        "cancel": ["PURCHASE_CONFIRM"],
    }
    permission_classes = [HasPermission]
    queryset = (
        Purchase.objects.select_related("supplier", "branch", "confirmed_by")
        .prefetch_related("items__medicine")
    )
    filterset_fields = ["lifecycle", "payment_status", "return_status", "supplier", "branch"]
    search_fields = ["number", "supplier_invoice_number", "supplier__name"]
    ordering_fields = ["business_date", "grand_total", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        return scoped_purchases(self.request.user, super().get_queryset())

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PurchaseWriteSerializer
        return PurchaseReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = PurchaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(
            PurchaseReadSerializer(purchase).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        purchase = self.get_object()
        serializer = PurchaseWriteSerializer(purchase, data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(PurchaseReadSerializer(purchase).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        purchase = self.get_object()
        payment_payload = request.data.get("payment")
        payment = None
        if payment_payload:
            account = FinancialAccount.objects.filter(
                id=payment_payload.get("account"), is_active=True
            ).first()
            if account is None:
                raise APIError("INVALID_ACCOUNT", "Payment account not found or inactive.")
            amount = Decimal(str(payment_payload.get("amount") or "0"))
            payment = {
                "amount": amount,
                "method": payment_payload.get("method", "CASH"),
                "account": account,
                "reference": payment_payload.get("reference", ""),
            }

        purchase = confirm_purchase(
            purchase=purchase,
            actor=request.user,
            allow_duplicate_invoice=bool(request.data.get("allow_duplicate_invoice")),
            duplicate_reason=request.data.get("duplicate_reason", ""),
            payment=payment,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PURCHASE_CONFIRMED",
            entity_type="purchase",
            entity_id=purchase.id,
            after={"number": purchase.number or "", "grand_total": str(purchase.grand_total)},
            branch=purchase.branch,
            request=request,
        )
        return Response(PurchaseReadSerializer(purchase).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        purchase = cancel_purchase(
            purchase=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PURCHASE_CANCELLED",
            entity_type="purchase",
            entity_id=purchase.id,
            after={"number": purchase.number or "", "reason": request.data.get("reason", "")},
            branch=purchase.branch,
            request=request,
        )
        return Response(PurchaseReadSerializer(purchase).data)


class SupplierPaymentViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["PURCHASE_PAY"],
        "retrieve": ["PURCHASE_PAY"],
        "create": ["PURCHASE_PAY"],
        "reverse": ["PURCHASE_PAY"],
    }
    permission_classes = [HasPermission]
    queryset = SupplierPayment.objects.select_related(
        "supplier", "branch", "account"
    ).prefetch_related("allocations__purchase")
    filterset_class = SupplierPaymentFilter
    search_fields = ["number", "reference", "supplier__name"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = SupplierPaymentReadSerializer

    def get_queryset(self):
        return scoped_purchases(self.request.user, super().get_queryset())

    def create(self, request, *args, **kwargs):
        serializer = SupplierPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        supplier = Supplier.objects.filter(id=data["supplier"]).first()
        if supplier is None:
            raise APIError("INVALID_SUPPLIER", "Supplier not found.")
        account = FinancialAccount.objects.filter(id=data["account"], is_active=True).first()
        if account is None:
            raise APIError("INVALID_ACCOUNT", "Payment account not found or inactive.")
        from apps.branches.models import Branch

        branch = Branch.objects.filter(id=data["branch"]).first()
        if branch is None:
            raise APIError("INVALID_BRANCH", "Branch not found.")

        allocations = None
        if data.get("allocations"):
            allocations = []
            for row in data["allocations"]:
                purchase = Purchase.objects.filter(id=row["purchase"]).first()
                if purchase is None:
                    raise APIError("INVALID_PURCHASE", "Allocation purchase not found.")
                allocations.append({"purchase": purchase, "amount": row["amount"]})

        payment = record_supplier_payment(
            supplier=supplier,
            branch=branch,
            amount=data["amount"],
            method=data["method"],
            account=account,
            business_date=data.get("business_date"),
            reference=data.get("reference", ""),
            allocations=allocations,
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SUPPLIER_PAYMENT",
            entity_type="supplier_payment",
            entity_id=payment.id,
            after={"number": payment.number or "", "amount": str(payment.amount), "method": payment.method},
            branch=payment.branch,
            request=request,
        )
        return Response(SupplierPaymentReadSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        payment = reverse_supplier_payment(
            payment=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SUPPLIER_PAYMENT_REVERSED",
            entity_type="supplier_payment",
            entity_id=payment.id,
            after={"number": payment.number or "", "amount": str(payment.amount)},
            branch=payment.branch,
            request=request,
        )
        return Response(SupplierPaymentReadSerializer(payment).data)


class PurchaseReturnViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["PRET_VIEW"],
        "retrieve": ["PRET_VIEW"],
        "create": ["PRET_CONFIRM"],
        "confirm": ["PRET_CONFIRM"],
    }
    permission_classes = [HasPermission]
    queryset = PurchaseReturn.objects.select_related("supplier", "purchase", "branch").prefetch_related(
        "items__purchase_item__medicine"
    )
    filterset_fields = ["supplier", "branch", "status", "reason_code"]
    search_fields = ["number", "purchase__number", "supplier__name"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = PurchaseReturnReadSerializer

    def get_queryset(self):
        return scoped_purchases(self.request.user, super().get_queryset())

    def create(self, request, *args, **kwargs):
        serializer = PurchaseReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            existing = PurchaseReturn.objects.filter(idempotency_key=idempotency_key).first()
            if existing is not None:
                return Response(
                    PurchaseReturnReadSerializer(existing).data, status=status.HTTP_201_CREATED
                )
        purchase_return = serializer.save()
        purchase_return.idempotency_key = idempotency_key or purchase_return.idempotency_key
        purchase_return.save(update_fields=["idempotency_key", "updated_at"])
        log_action(
            actor=request.user,
            action="PURCHASE_RETURN_CREATED",
            entity_type="purchase_return",
            entity_id=purchase_return.id,
            after={"number": purchase_return.number or "", "grand_total": str(purchase_return.grand_total)},
            branch=purchase_return.branch,
            request=request,
        )
        return Response(
            PurchaseReturnReadSerializer(purchase_return).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        purchase_return = confirm_purchase_return(
            purchase_return=self.get_object(),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PURCHASE_RETURN_CONFIRMED",
            entity_type="purchase_return",
            entity_id=purchase_return.id,
            after={"number": purchase_return.number or "", "grand_total": str(purchase_return.grand_total)},
            branch=purchase_return.branch,
            request=request,
        )
        return Response(PurchaseReturnReadSerializer(purchase_return).data)


class PayableAgingView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["PURCHASE_VIEW"]

    BUCKETS = ["current", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"]

    def get(self, request):
        queryset = Purchase.objects.select_related("supplier").filter(
            lifecycle=PurchaseStatus.CONFIRMED
        )
        queryset = scoped_purchases(request.user, queryset)
        today = timezone.localdate()

        per_supplier: dict[str, dict] = {}
        for purchase in queryset:
            outstanding = purchase.grand_total - purchase.paid_total
            if outstanding <= 0:
                continue
            due_date = purchase.business_date + timedelta(days=purchase.supplier.credit_days)
            overdue_days = (today - due_date).days
            if overdue_days <= 0:
                bucket = "current"
            elif overdue_days <= 30:
                bucket = "days_1_30"
            elif overdue_days <= 60:
                bucket = "days_31_60"
            elif overdue_days <= 90:
                bucket = "days_61_90"
            else:
                bucket = "days_90_plus"

            row = per_supplier.setdefault(
                str(purchase.supplier_id),
                {
                    "supplier": purchase.supplier_id,
                    "supplier_name": purchase.supplier.name,
                    "supplier_code": purchase.supplier.code,
                    **{key: Decimal("0") for key in self.BUCKETS},
                    "total": Decimal("0"),
                },
            )
            row[bucket] += outstanding
            row["total"] += outstanding

        results = sorted(per_supplier.values(), key=lambda row: row["supplier_name"])
        totals = {key: sum((row[key] for row in results), Decimal("0")) for key in self.BUCKETS}
        totals["total"] = sum((row["total"] for row in results), Decimal("0"))

        def as_strings(row: dict) -> dict:
            return {
                key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
            }

        return Response(
            {
                "count": len(results),
                "totals": as_strings(totals),
                "results": [as_strings(row) for row in results],
            }
        )


class PurchasePdfView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["PURCHASE_VIEW"]

    def get(self, request, purchase_id):
        from django.http import HttpResponse

        from apps.purchases.pdf import build_purchase_pdf

        queryset = (
            Purchase.objects.select_related("supplier", "branch", "confirmed_by")
            .prefetch_related("items__medicine", "items__batch")
        )
        purchase = scoped_purchases(request.user, queryset).filter(id=purchase_id).first()
        if purchase is None:
            raise APIError("NOT_FOUND", "Purchase not found.")

        pdf = build_purchase_pdf(purchase)

        response = HttpResponse(pdf, content_type="application/pdf")
        filename = purchase.number or f"purchase-{purchase.id}"
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response
