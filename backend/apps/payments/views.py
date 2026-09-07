from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.audit.services import log_action
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.payments.models import Cheque, Payment, PaymentStatus
from apps.payments.serializers import (
    ChequeCreateSerializer,
    ChequeReadSerializer,
    CustomerPaymentCreateSerializer,
    CustomerPaymentReadSerializer,
)
from apps.payments.services import record_customer_payment, reverse_customer_payment
from apps.sales.models import Customer, SalesInvoice


class CustomerPaymentViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["PAYMENT_VIEW"],
        "retrieve": ["PAYMENT_VIEW"],
        "create": ["PAYMENT_COLLECT"],
        "reverse": ["PAYMENT_REVERSE"],
    }
    permission_classes = [HasPermission]
    queryset = Payment.objects.select_related("customer", "branch", "account").prefetch_related(
        "allocations__invoice"
    )
    filterset_fields = ["customer", "branch", "status", "method"]
    search_fields = ["number", "reference", "customer__name"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = CustomerPaymentReadSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return super().get_queryset()
        return super().get_queryset().filter(branch_id__in=user.branch_ids)

    def create(self, request, *args, **kwargs):
        serializer = CustomerPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        customer = Customer.objects.filter(id=data["customer"]).first()
        if customer is None:
            raise APIError("INVALID_CUSTOMER", "Customer not found.")
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
                invoice = SalesInvoice.objects.filter(id=row["invoice"]).first()
                if invoice is None:
                    raise APIError("INVALID_INVOICE", "Allocation invoice not found.")
                allocations.append({"invoice": invoice, "amount": row["amount"]})

        payment = record_customer_payment(
            customer=customer,
            branch=branch,
            amount=data["amount"],
            method=data["method"],
            account=account,
            business_date=data.get("business_date"),
            reference=data.get("reference", ""),
            allocations=allocations,
            actor=request.user,
            collector=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="CUSTOMER_PAYMENT",
            entity_type="customer_payment",
            entity_id=payment.id,
            after={"number": payment.number or "", "amount": str(payment.amount), "method": payment.method},
            branch=payment.branch,
            request=request,
        )
        return Response(
            CustomerPaymentReadSerializer(payment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        payment = reverse_customer_payment(
            payment=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="CUSTOMER_PAYMENT_REVERSED",
            entity_type="customer_payment",
            entity_id=payment.id,
            after={"number": payment.number or "", "amount": str(payment.amount)},
            branch=payment.branch,
            request=request,
        )
        return Response(CustomerPaymentReadSerializer(payment).data)


class DailyCollectionView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["PAYMENT_VIEW"]

    def get(self, request):
        from django.db.models import Count, Sum
        from django.utils import timezone

        date = request.query_params.get("date") or timezone.localdate().isoformat()
        queryset = Payment.objects.filter(status=PaymentStatus.ACTIVE, business_date=date)
        user = request.user
        if not (user.is_superuser or user.has_all_branch_scope):
            queryset = queryset.filter(branch_id__in=user.branch_ids)
        if request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=request.query_params["branch"])

        by_method = list(
            queryset.values("method")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("method")
        )
        by_collector = list(
            queryset.values("collector__full_name", "collector_id")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("collector__full_name")
        )
        grand_total = queryset.aggregate(total=Sum("amount"))["total"]

        return Response(
            {
                "date": date,
                "payment_count": queryset.count(),
                "total": str(grand_total or 0),
                "by_method": [
                    {"method": row["method"], "total": str(row["total"]), "count": row["count"]}
                    for row in by_method
                ],
                "by_collector": [
                    {
                        "collector": row["collector_id"],
                        "collector_name": row["collector__full_name"] or "—",
                        "total": str(row["total"]),
                        "count": row["count"],
                    }
                    for row in by_collector
                ],
            }
        )


class ChequeViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["CHEQUE_VIEW"],
        "retrieve": ["CHEQUE_VIEW"],
        "create": ["CHEQUE_MANAGE"],
        "deposit": ["CHEQUE_MANAGE"],
        "clear": ["CHEQUE_MANAGE"],
        "bounce": ["CHEQUE_MANAGE"],
        "stop": ["CHEQUE_MANAGE"],
        "mark_paid": ["CHEQUE_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = ChequeReadSerializer
    queryset = Cheque.objects.all()
    filterset_fields = ["direction", "status", "customer", "supplier"]
    search_fields = ["number", "bank_name", "customer__name", "supplier__name"]
    ordering_fields = ["date_issued", "amount", "created_at", "status"]
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):
        from apps.payments.services import create_cheque

        serializer = ChequeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cheque = create_cheque(validated=serializer.validated_data, actor=request.user)
        return Response(ChequeReadSerializer(cheque).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def deposit(self, request, pk=None):
        from apps.payments.services import deposit_cheque

        cheque = deposit_cheque(
            self.get_object(),
            actor=request.user,
            notes=request.data.get("notes", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user, action="CHEQUE_DEPOSITED", entity_type="cheque", entity_id=cheque.id,
            after={"number": cheque.number, "status": cheque.status}, request=request,
        )
        return Response(ChequeReadSerializer(cheque).data)

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        from apps.payments.services import clear_cheque

        cheque = clear_cheque(
            self.get_object(),
            actor=request.user,
            notes=request.data.get("notes", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user, action="CHEQUE_CLEARED", entity_type="cheque", entity_id=cheque.id,
            after={"number": cheque.number, "status": cheque.status}, request=request,
        )
        return Response(ChequeReadSerializer(cheque).data)

    @action(detail=True, methods=["post"])
    def bounce(self, request, pk=None):
        from apps.payments.services import bounce_cheque

        cheque = bounce_cheque(
            self.get_object(),
            actor=request.user,
            notes=request.data.get("notes", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user, action="CHEQUE_BOUNCED", entity_type="cheque", entity_id=cheque.id,
            after={"number": cheque.number, "status": cheque.status}, request=request,
        )
        return Response(ChequeReadSerializer(cheque).data)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        from apps.payments.services import stop_cheque

        cheque = stop_cheque(
            self.get_object(),
            actor=request.user,
            notes=request.data.get("notes", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user, action="CHEQUE_STOPPED", entity_type="cheque", entity_id=cheque.id,
            after={"number": cheque.number, "status": cheque.status}, request=request,
        )
        return Response(ChequeReadSerializer(cheque).data)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        from apps.payments.services import mark_cheque_paid

        cheque = mark_cheque_paid(
            self.get_object(),
            actor=request.user,
            notes=request.data.get("notes", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user, action="CHEQUE_PAID", entity_type="cheque", entity_id=cheque.id,
            after={"number": cheque.number, "status": cheque.status}, request=request,
        )
        return Response(ChequeReadSerializer(cheque).data)


class PaymentReceiptPdfView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["PAYMENT_VIEW"]

    def get(self, request, payment_id):
        from django.http import HttpResponse

        from apps.payments.pdf import build_receipt_pdf

        queryset = Payment.objects.select_related(
            "customer", "branch", "account", "collector"
        ).prefetch_related("allocations__invoice")
        user = request.user
        if not (user.is_superuser or user.has_all_branch_scope):
            queryset = queryset.filter(branch_id__in=user.branch_ids)
        payment = queryset.filter(id=payment_id).first()
        if payment is None:
            raise APIError("NOT_FOUND", "Receipt not found.")

        pdf = build_receipt_pdf(payment)

        response = HttpResponse(pdf, content_type="application/pdf")
        filename = payment.number or f"receipt-{payment.id}"
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response
