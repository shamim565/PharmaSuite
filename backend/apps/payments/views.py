from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.payments.models import Payment, PaymentStatus
from apps.payments.serializers import (
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
        return Response(
            CustomerPaymentReadSerializer(payment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        payment = reverse_customer_payment(
            payment=self.get_object(), actor=request.user, reason=request.data.get("reason", "")
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
