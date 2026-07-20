from decimal import Decimal

from django.db.models import F
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.sales.models import Customer, SalesInvoice
from apps.sales.serializers import (
    CustomerLedgerEntrySerializer,
    CustomerSerializer,
    SalesInvoiceReadSerializer,
    SalesInvoiceWriteSerializer,
)
from apps.sales.services import cancel_sale, confirm_sale, fefo_candidates


def scoped_sales(user, queryset):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(branch_id__in=user.branch_ids)


class CustomerViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["CUSTOMER_VIEW"],
        "retrieve": ["CUSTOMER_VIEW"],
        "create": ["CUSTOMER_MANAGE"],
        "update": ["CUSTOMER_MANAGE"],
        "partial_update": ["CUSTOMER_MANAGE"],
        "ledger": ["CUSTOMER_VIEW"],
    }
    permission_classes = [HasPermission]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    filterset_fields = ["is_active", "customer_type", "price_tier", "area", "credit_hold"]
    search_fields = ["code", "name", "phone", "area"]
    ordering_fields = ["name", "code", "balance_cache", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        customer = self.get_object()
        entries = customer.ledger_entries.select_related("branch").order_by("-created_at", "-id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            entries = entries.filter(business_date__gte=date_from)
        if date_to:
            entries = entries.filter(business_date__lte=date_to)

        entries = list(entries[:500])
        balance = Decimal("0")
        rows = []
        for entry in reversed(entries):
            balance += entry.amount_delta
            row = CustomerLedgerEntrySerializer(entry).data
            row["running_balance"] = balance
            rows.append(row)
        rows.reverse()
        return Response(
            {"balance": str(customer.balance_cache), "count": len(rows), "results": rows}
        )


class SalesInvoiceViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["SALE_VIEW"],
        "retrieve": ["SALE_VIEW"],
        "create": ["SALE_CREATE"],
        "update": ["SALE_CREATE"],
        "partial_update": ["SALE_CREATE"],
        "confirm": ["SALE_CONFIRM"],
        "cancel": ["SALE_CANCEL"],
        "fefo": ["SALE_VIEW"],
    }
    permission_classes = [HasPermission]
    queryset = SalesInvoice.objects.select_related("customer", "branch").prefetch_related(
        "items__medicine", "items__batch"
    )
    filterset_fields = ["lifecycle", "payment_status", "return_status", "customer", "branch"]
    search_fields = ["number", "customer__name", "customer__code"]
    ordering_fields = ["business_date", "grand_total", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        return scoped_sales(self.request.user, super().get_queryset())

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SalesInvoiceWriteSerializer
        return SalesInvoiceReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = SalesInvoiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(
            SalesInvoiceReadSerializer(invoice).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        invoice = self.get_object()
        serializer = SalesInvoiceWriteSerializer(invoice, data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(SalesInvoiceReadSerializer(invoice).data)

    @action(detail=False, methods=["get"])
    def fefo(self, request):
        branch_id = request.query_params.get("branch")
        medicine_id = request.query_params.get("medicine")
        if not branch_id or not medicine_id:
            raise APIError("MISSING_PARAMS", "branch and medicine are required.")
        from apps.branches.models import Branch
        from apps.catalog.models import Medicine

        branch = Branch.objects.filter(id=branch_id).first()
        medicine = Medicine.objects.filter(id=medicine_id).first()
        if branch is None or medicine is None:
            raise APIError("NOT_FOUND", "Branch or medicine not found.")
        return Response({"results": fefo_candidates(branch, medicine)})

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        payment_payload = request.data.get("payment")
        payment = None
        if payment_payload and Decimal(str(payment_payload.get("amount") or "0")) > 0:
            account = FinancialAccount.objects.filter(
                id=payment_payload.get("account"), is_active=True
            ).first()
            if account is None:
                raise APIError("INVALID_ACCOUNT", "Payment account not found or inactive.")
            payment = {
                "amount": Decimal(str(payment_payload["amount"])),
                "method": payment_payload.get("method", "CASH"),
                "account": account,
                "reference": payment_payload.get("reference", ""),
            }

        invoice = confirm_sale(
            invoice=invoice,
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
            payment=payment,
            allow_credit_override=bool(request.data.get("allow_credit_override")),
            credit_override_reason=request.data.get("credit_override_reason", ""),
        )
        return Response(SalesInvoiceReadSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        invoice = cancel_sale(
            invoice=self.get_object(), actor=request.user, reason=request.data.get("reason", "")
        )
        return Response(SalesInvoiceReadSerializer(invoice).data)


class DueListView(APIView):
    """Open invoices with aging for the collection desk."""

    permission_classes = [HasPermission]
    required_permissions = ["CUSTOMER_VIEW"]

    def get(self, request):
        queryset = (
            SalesInvoice.objects.select_related("customer", "branch")
            .filter(lifecycle="CONFIRMED", paid_total__lt=F("grand_total"))
        )
        queryset = scoped_sales(request.user, queryset)

        customer_id = request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if request.query_params.get("branch"):
            queryset = queryset.filter(branch_id=request.query_params["branch"])
        if request.query_params.get("search"):
            search = request.query_params["search"]
            queryset = queryset.filter(customer__name__icontains=search)

        min_overdue = request.query_params.get("min_overdue_days")
        overdue_days_filter = int(min_overdue) if min_overdue and min_overdue.isdigit() else None
        overdue_only = request.query_params.get("overdue_only") == "true"

        today = timezone.localdate()
        results = []
        total_outstanding = Decimal("0")
        total_overdue = Decimal("0")
        for invoice in queryset.order_by("due_date", "business_date"):
            outstanding = invoice.grand_total - invoice.paid_total
            if outstanding <= 0:
                continue
            due_date = invoice.due_date or invoice.business_date
            days_overdue = (today - due_date).days
            if overdue_only and days_overdue <= 0:
                continue
            if overdue_days_filter is not None and days_overdue < overdue_days_filter:
                continue

            if days_overdue <= 0:
                bucket = "current"
            elif days_overdue <= 30:
                bucket = "days_1_30"
            elif days_overdue <= 60:
                bucket = "days_31_60"
            elif days_overdue <= 90:
                bucket = "days_61_90"
            else:
                bucket = "days_90_plus"

            total_outstanding += outstanding
            if days_overdue > 0:
                total_overdue += outstanding

            results.append(
                {
                    "invoice": invoice.id,
                    "number": invoice.number,
                    "business_date": invoice.business_date,
                    "due_date": due_date,
                    "days_overdue": days_overdue,
                    "bucket": bucket,
                    "customer": invoice.customer_id,
                    "customer_name": invoice.customer.name,
                    "customer_code": invoice.customer.code,
                    "phone": invoice.customer.phone,
                    "branch": invoice.branch_id,
                    "branch_name": invoice.branch.name,
                    "grand_total": str(invoice.grand_total),
                    "paid_total": str(invoice.paid_total),
                    "outstanding": str(outstanding),
                    "payment_status": invoice.payment_status,
                }
            )

        return Response(
            {
                "count": len(results),
                "totals": {
                    "outstanding": str(total_outstanding),
                    "overdue": str(total_overdue),
                },
                "results": results,
            }
        )


class CustomerAdvanceView(APIView):
    """Customers holding an advance (negative ledger balance)."""

    permission_classes = [HasPermission]
    required_permissions = ["CUSTOMER_VIEW"]

    def get(self, request):
        customers = Customer.objects.filter(balance_cache__lt=0).order_by("name")
        results = [
            {
                "customer": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.code,
                "phone": customer.phone,
                "advance": str(-customer.balance_cache),
            }
            for customer in customers
        ]
        total = sum((Decimal(row["advance"]) for row in results), Decimal("0"))
        return Response({"count": len(results), "total": str(total), "results": results})


class ReceivableAgingView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["CUSTOMER_VIEW"]

    BUCKETS = ["current", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"]

    def get(self, request):
        queryset = SalesInvoice.objects.select_related("customer").filter(lifecycle="CONFIRMED")
        queryset = scoped_sales(request.user, queryset)
        today = timezone.localdate()

        per_customer: dict[str, dict] = {}
        for invoice in queryset:
            outstanding = invoice.grand_total - invoice.paid_total
            if outstanding <= 0:
                continue
            due_date = invoice.due_date or invoice.business_date
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

            row = per_customer.setdefault(
                str(invoice.customer_id),
                {
                    "customer": invoice.customer_id,
                    "customer_name": invoice.customer.name,
                    "customer_code": invoice.customer.code,
                    "phone": invoice.customer.phone,
                    **{key: Decimal("0") for key in self.BUCKETS},
                    "total": Decimal("0"),
                },
            )
            row[bucket] += outstanding
            row["total"] += outstanding

        def as_strings(row: dict) -> dict:
            return {
                key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
            }

        results = sorted(per_customer.values(), key=lambda row: row["customer_name"])
        totals = {key: sum((row[key] for row in results), Decimal("0")) for key in self.BUCKETS}
        totals["total"] = sum((row["total"] for row in results), Decimal("0"))
        return Response(
            {
                "count": len(results),
                "totals": as_strings(totals),
                "results": [as_strings(row) for row in results],
            }
        )
