from decimal import Decimal

from django.db.models import F
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.audit.services import log_action
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.schema import object_response, pdf_response
from apps.common.settings_service import get_setting_bool
from apps.common.viewsets import PermissionMappedMixin
from apps.sales.models import Customer, SalesInvoice, SalesInvoiceStatus, SalesReturn
from apps.sales.serializers import (
    CustomerLedgerEntrySerializer,
    CustomerSerializer,
    DirectReturnCreateSerializer,
    SalesInvoiceReadSerializer,
    SalesInvoiceWriteSerializer,
    SalesReturnCreateSerializer,
    SalesReturnReadSerializer,
)
from apps.sales.services import (
    cancel_sale,
    confirm_sale,
    confirm_sales_return,
    create_direct_return,
    create_sales_return,
    fefo_candidates,
    mark_invoice_delivered,
)


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
        "statement": ["CUSTOMER_VIEW"],
    }
    permission_classes = [HasPermission]
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    filterset_fields = ["is_active", "customer_type", "price_tier", "area", "credit_hold"]
    search_fields = ["code", "name", "phone", "area"]
    ordering_fields = ["name", "code", "balance_cache", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        from django.http import HttpResponse

        customer = self.get_object()
        entries = list(
            customer.ledger_entries.order_by("created_at", "id")
        )
        balance = Decimal("0")
        rows = []
        for entry in entries:
            balance += entry.amount_delta
            rows.append(
                {
                    "date": entry.business_date.isoformat(),
                    "number": entry.source_number or entry.entry_type,
                    "description": entry.entry_type,
                    "amount": f"{entry.amount_delta:.2f}",
                    "balance": f"{balance:.2f}",
                }
            )
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{customer.code}-statement.csv"'
        import csv

        writer = csv.DictWriter(
            response, fieldnames=["date", "number", "description", "amount", "balance"]
        )
        writer.writeheader()
        writer.writerows(rows)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        customer = self.get_object()
        log_action(
            actor=request.user,
            action="CUSTOMER_UPDATED",
            entity_type="customer",
            entity_id=customer.id,
            after={"code": customer.code},
            request=request,
        )
        return response

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
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["SALE_VIEW"],
        "retrieve": ["SALE_VIEW"],
        "create": ["SALE_CREATE"],
        "update": ["SALE_CREATE"],
        "partial_update": ["SALE_CREATE"],
        "destroy": ["SALE_CREATE"],
        "confirm": ["SALE_CONFIRM"],
        "cancel": ["SALE_CANCEL"],
        "mark_delivered": ["SALE_CONFIRM"],
        "fefo": ["SALE_VIEW"],
    }
    permission_classes = [HasPermission]
    queryset = SalesInvoice.objects.select_related("customer", "branch", "confirmed_by").prefetch_related(
        "items__medicine", "items__batch"
    )
    filterset_fields = ["lifecycle", "payment_status", "return_status", "customer", "branch"]
    search_fields = ["number", "customer__name", "customer__code"]
    ordering_fields = ["business_date", "grand_total", "created_at"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        queryset = scoped_sales(self.request.user, super().get_queryset())
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(business_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(business_date__lte=date_to)
        return queryset

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SalesInvoiceWriteSerializer
        return SalesInvoiceReadSerializer

    def destroy(self, request, *args, **kwargs):
        invoice = self.get_object()
        if invoice.lifecycle != SalesInvoiceStatus.DRAFT:
            raise APIError(
                "INVALID_STATUS_TRANSITION", "Only draft invoices can be deleted."
            )
        log_action(
            actor=request.user,
            action="SALE_DRAFT_DELETED",
            entity_type="sales_invoice",
            entity_id=invoice.id,
            before={
                "number": invoice.number or "",
                "customer": invoice.customer_id,
                "grand_total": str(invoice.grand_total),
            },
            branch=invoice.branch,
            request=request,
        )
        invoice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        self._validate_fefo_permission(request)
        serializer = SalesInvoiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._ensure_branch_in_scope(serializer.validated_data["branch"])
        invoice = serializer.save()
        return Response(
            SalesInvoiceReadSerializer(invoice).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        self._validate_fefo_permission(request)
        invoice = self.get_object()
        serializer = SalesInvoiceWriteSerializer(invoice, data=request.data)
        serializer.is_valid(raise_exception=True)
        self._ensure_branch_in_scope(serializer.validated_data["branch"])
        invoice = serializer.save()
        return Response(SalesInvoiceReadSerializer(invoice).data)

    @staticmethod
    def _validate_fefo_permission(request):
        items = request.data.get("items") or []
        selects_batch = any(
            isinstance(item, dict) and item.get("batch") for item in items
        )
        if selects_batch:
            user = request.user
            has_permission = user.is_superuser or "INV_OVERRIDE_FEFO" in user.effective_permission_codes
            if not has_permission:
                raise APIError(
                    "PERMISSION_DENIED",
                    "You do not have permission to override FEFO batch selection.",
                    status_code=403,
                )

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
        self._ensure_branch_in_scope(branch.id)
        return Response({"results": fefo_candidates(branch, medicine)})

    def _ensure_branch_in_scope(self, branch_id) -> None:
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return
        if str(branch_id) not in {str(branch) for branch in user.branch_ids}:
            raise APIError(
                "BRANCH_SCOPE_EXCEEDED",
                "You cannot post sales for a branch outside your scope.",
                status_code=403,
            )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        allow_credit_override = bool(request.data.get("allow_credit_override"))
        if allow_credit_override:
            user = request.user
            if not (
                user.is_superuser
                or "SALE_OVERRIDE_CREDIT" in user.effective_permission_codes
            ):
                raise APIError(
                    "PERMISSION_DENIED",
                    "Permission SALE_OVERRIDE_CREDIT is required to override credit controls.",
                    status_code=403,
                )
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
            prescription_number=request.data.get("prescription_number", ""),
            rx_override=bool(request.data.get("rx_override")),
            rx_override_reason=request.data.get("rx_override_reason", ""),
        )
        log_action(
            actor=request.user,
            action="SALE_CONFIRMED",
            entity_type="sales_invoice",
            entity_id=invoice.id,
            after={"number": invoice.number or "", "grand_total": str(invoice.grand_total), "paid_total": str(invoice.paid_total)},
            branch=invoice.branch,
            request=request,
        )
        return Response(SalesInvoiceReadSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        invoice = cancel_sale(
            invoice=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SALE_CANCELLED",
            entity_type="sales_invoice",
            entity_id=invoice.id,
            after={"number": invoice.number or "", "reason": request.data.get("reason", "")},
            branch=invoice.branch,
            request=request,
        )
        return Response(SalesInvoiceReadSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="mark-delivered")
    def mark_delivered(self, request, pk=None):
        invoice = mark_invoice_delivered(invoice=self.get_object(), actor=request.user)
        return Response(SalesInvoiceReadSerializer(invoice).data)


@pdf_response
class InvoicePdfView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["SALE_VIEW"]

    def get(self, request, invoice_id):
        from django.http import HttpResponse

        from apps.sales.pdf import build_invoice_pdf

        queryset = SalesInvoice.objects.select_related("customer", "branch", "confirmed_by").prefetch_related(
            "items__medicine", "items__batch"
        )
        invoice = scoped_sales(request.user, queryset).filter(id=invoice_id).first()
        if invoice is None:
            raise APIError("NOT_FOUND", "Invoice not found.")

        include_cost = request.user.is_superuser or (
            "STOCK_VIEW_COST" in request.user.effective_permission_codes
        )
        pdf = build_invoice_pdf(invoice, include_cost=include_cost)

        response = HttpResponse(pdf, content_type="application/pdf")
        filename = invoice.number or f"invoice-{invoice.id}"
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response


@object_response
class SalesConfigView(APIView):
    """Client-safe sales config (available to any user who can view sales)."""

    permission_classes = [HasPermission]
    required_permissions = ["SALE_VIEW"]

    def get(self, request):
        return Response(
            {"vat_enabled": get_setting_bool("SALES_VAT_ENABLED", default=False)}
        )


@object_response
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

        totals = {
            "outstanding": str(total_outstanding),
            "overdue": str(total_overdue),
        }
        page_size_raw = request.query_params.get("page_size")
        if page_size_raw and page_size_raw.isdigit():
            page_size = max(int(page_size_raw), 1)
            page_raw = request.query_params.get("page", "1")
            page = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
            offset = (page - 1) * page_size
            return Response(
                {
                    "count": len(results),
                    "page": page,
                    "page_size": page_size,
                    "next": offset + page_size < len(results),
                    "previous": page > 1,
                    "totals": totals,
                    "results": results[offset : offset + page_size],
                }
            )
        return Response(
            {
                "count": len(results),
                "totals": totals,
                "results": results,
            }
        )


@object_response
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


@object_response
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


class SalesReturnViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["SRET_VIEW"],
        "retrieve": ["SRET_VIEW"],
        "create": ["SRET_CONFIRM"],
        "destroy": ["SRET_CONFIRM"],
        "confirm": ["SRET_CONFIRM"],
        "direct": ["SRET_NO_INVOICE"],
    }
    permission_classes = [HasPermission]
    queryset = SalesReturn.objects.select_related("customer", "invoice", "branch").prefetch_related(
        "items__invoice_item__medicine", "items__batch__medicine"
    )
    filterset_fields = ["customer", "branch", "status", "reason_code"]
    search_fields = ["number", "invoice__number", "customer__name"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = SalesReturnReadSerializer

    def get_queryset(self):
        return scoped_sales(self.request.user, super().get_queryset())

    def create(self, request, *args, **kwargs):
        serializer = SalesReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invoice = SalesInvoice.objects.filter(id=data["invoice"]).first()
        if invoice is None:
            raise APIError("INVALID_INVOICE", "Invoice not found.")
        refund_account = None
        if data.get("refund_account"):
            refund_account = FinancialAccount.objects.filter(id=data["refund_account"]).first()
            if refund_account is None:
                raise APIError("INVALID_ACCOUNT", "Refund account not found.")

        sales_return = create_sales_return(
            invoice=invoice,
            reason_code=data["reason_code"],
            refund_method=data["refund_method"],
            refund_account=refund_account,
            business_date=data.get("business_date"),
            notes=data.get("notes", ""),
            items_data=data["items"],
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SALES_RETURN_CREATED",
            entity_type="sales_return",
            entity_id=sales_return.id,
            after={"number": sales_return.number or "", "grand_total": str(sales_return.grand_total)},
            branch=sales_return.branch,
            request=request,
        )
        return Response(
            SalesReturnReadSerializer(sales_return).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["post"], url_path="direct")
    def direct(self, request):
        serializer = DirectReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.branches.models import Branch
        from apps.catalog.models import MedicineBatch

        customer = Customer.objects.filter(id=data["customer"], is_active=True).first()
        if customer is None:
            raise APIError("INVALID_CUSTOMER", "Customer not found or inactive.")
        branch = Branch.objects.filter(id=data["branch"]).first()
        if branch is None:
            raise APIError("INVALID_BRANCH", "Branch not found.")

        user = request.user
        if not (user.is_superuser or user.has_all_branch_scope):
            if str(branch.id) not in {str(b) for b in user.branch_ids}:
                raise APIError(
                    "BRANCH_SCOPE_EXCEEDED",
                    "You cannot return stock for a branch outside your scope.",
                    status_code=403,
                )

        refund_account = None
        if data.get("refund_account"):
            refund_account = FinancialAccount.objects.filter(id=data["refund_account"]).first()
            if refund_account is None:
                raise APIError("INVALID_ACCOUNT", "Refund account not found.")

        items_data = []
        for row in data["items"]:
            batch = (
                MedicineBatch.objects.select_related("medicine").filter(id=row["batch"]).first()
            )
            if batch is None:
                raise APIError("INVALID_BATCH", "Batch not found.")
            if str(batch.medicine_id) != str(row["medicine"]):
                raise APIError("INVALID_BATCH", "Batch does not belong to the selected medicine.")
            items_data.append({**row, "batch": batch, "medicine": batch.medicine})

        sales_return = create_direct_return(
            customer=customer,
            branch=branch,
            reason_code=data["reason_code"],
            refund_method=data["refund_method"],
            refund_account=refund_account,
            business_date=data.get("business_date"),
            notes=data.get("notes", ""),
            items_data=items_data,
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SALES_RETURN_CREATED",
            entity_type="sales_return",
            entity_id=sales_return.id,
            after={
                "number": sales_return.number or "",
                "direct": True,
                "grand_total": str(sales_return.grand_total),
            },
            branch=sales_return.branch,
            request=request,
        )
        return Response(
            SalesReturnReadSerializer(sales_return).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        sales_return = confirm_sales_return(
            sales_return=self.get_object(),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="SALES_RETURN_CONFIRMED",
            entity_type="sales_return",
            entity_id=sales_return.id,
            after={"number": sales_return.number or "", "grand_total": str(sales_return.grand_total)},
            branch=sales_return.branch,
            request=request,
        )
        return Response(SalesReturnReadSerializer(sales_return).data)

    def destroy(self, request, *args, **kwargs):
        sales_return = self.get_object()
        if sales_return.status != "DRAFT":
            raise APIError("INVALID_STATUS_TRANSITION", "Only draft returns can be deleted.")
        sales_return.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)