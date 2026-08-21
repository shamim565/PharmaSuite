from datetime import timedelta
from decimal import Decimal

import django_filters
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_action
from apps.catalog.models import BatchStatus
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.inventory.models import (
    InventoryTransaction,
    StockAdjustment,
    StockBalance,
    StockTransfer,
)
from apps.inventory.serializers import (
    InventoryTransactionSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentReadSerializer,
    StockBalanceSerializer,
    StockTransferCreateSerializer,
    StockTransferReadSerializer,
)
from apps.inventory.services import (
    approve_stock_adjustment,
    confirm_stock_transfer,
    create_stock_adjustment,
    create_stock_transfer,
    ledger_quantities,
    reject_stock_adjustment,
    reverse_stock_adjustment,
)

DEFAULT_NEAR_EXPIRY_DAYS = 90
MAX_NEAR_EXPIRY_SCAN_DAYS = 366


def scoped_branch_ids(user):
    if user.is_superuser or user.has_all_branch_scope:
        return None
    return user.branch_ids


class InventoryTransactionFilter(django_filters.FilterSet):
    """Adds business-date range filters (used by the stock movement report)."""

    date_from = django_filters.DateFilter(field_name="business_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="business_date", lookup_expr="lte")

    class Meta:
        model = InventoryTransaction
        fields = [
            "branch",
            "medicine",
            "batch",
            "entry_type",
            "pool",
            "transaction_group_id",
            "date_from",
            "date_to",
        ]


class InventoryTransactionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]
    serializer_class = InventoryTransactionSerializer
    queryset = InventoryTransaction.objects.select_related(
        "branch", "medicine", "batch", "created_by"
    )
    filterset_class = InventoryTransactionFilter
    search_fields = ["source_number", "medicine__name", "medicine__code", "batch__batch_number"]
    ordering_fields = ["created_at", "business_date", "qty_delta"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        branches = scoped_branch_ids(self.request.user)
        if branches is not None:
            qs = qs.filter(branch_id__in=branches)

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(business_date__gte=date_from)
        if date_to:
            qs = qs.filter(business_date__lte=date_to)
        return qs


class StockBalanceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]
    serializer_class = StockBalanceSerializer
    queryset = StockBalance.objects.select_related("branch", "medicine", "batch")
    filterset_fields = ["branch", "medicine", "batch"]
    search_fields = ["medicine__name", "medicine__code", "batch__batch_number"]
    ordering_fields = ["updated_at", "qty_on_hand"]
    ordering = ["medicine__name", "batch__expiry_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        branches = scoped_branch_ids(self.request.user)
        if branches is not None:
            qs = qs.filter(branch_id__in=branches)
        if self.request.query_params.get("include_zero") != "true":
            qs = qs.filter(Q(qty_on_hand__gt=0) | Q(qty_promo__gt=0) | Q(qty_quarantine__gt=0))
        return qs


def _summary_rows(request, *, force_low: bool = False) -> list[dict]:
    qs = StockBalance.objects.all()
    branches = scoped_branch_ids(request.user)
    if branches is not None:
        qs = qs.filter(branch_id__in=branches)
    if request.query_params.get("branch"):
        qs = qs.filter(branch_id=request.query_params["branch"])

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(medicine__name__icontains=search) | Q(medicine__code__icontains=search))

    aggregated = (
        qs.values(
            "branch_id",
            "branch__name",
            "medicine_id",
            "medicine__name",
            "medicine__code",
            "medicine__reorder_level",
        )
        .annotate(
            qty_on_hand=Coalesce(Sum("qty_on_hand"), Decimal("0")),
            qty_promo=Coalesce(Sum("qty_promo"), Decimal("0")),
            qty_quarantine=Coalesce(Sum("qty_quarantine"), Decimal("0")),
        )
        .order_by("medicine__name")
    )

    if force_low or request.query_params.get("low_stock") == "true":
        aggregated = aggregated.filter(
            medicine__reorder_level__gt=0, qty_on_hand__lte=F("medicine__reorder_level")
        )

    results = []
    for row in aggregated:
        total = row["qty_on_hand"] or Decimal("0")
        reorder = row["medicine__reorder_level"] or Decimal("0")
        results.append(
            {
                "branch": row["branch_id"],
                "branch_name": row["branch__name"],
                "medicine": row["medicine_id"],
                "medicine_name": row["medicine__name"],
                "medicine_code": row["medicine__code"],
                "qty_on_hand": total,
                "qty_promo": row["qty_promo"] or Decimal("0"),
                "qty_quarantine": row["qty_quarantine"] or Decimal("0"),
                "reorder_level": reorder,
                "is_low_stock": reorder > 0 and total <= reorder,
                "is_out_of_stock": total <= 0,
            }
        )
    return results


def _rows_response(request, rows: list[dict]) -> Response:
    """Return ``{count, results}``; honour optional page/page_size params."""
    count = len(rows)
    page_size_raw = request.query_params.get("page_size")
    if page_size_raw and page_size_raw.isdigit():
        page_size = max(int(page_size_raw), 1)
        page_raw = request.query_params.get("page", "1")
        page = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
        offset = (page - 1) * page_size
        return Response(
            {
                "count": count,
                "page": page,
                "page_size": page_size,
                "next": offset + page_size < count,
                "previous": page > 1,
                "results": rows[offset : offset + page_size],
            }
        )
    return Response({"count": count, "results": rows})


class StockSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        return _rows_response(request, _summary_rows(request))


class LowStockReportView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        return _rows_response(request, _summary_rows(request, force_low=True))


def _batch_report_rows(request, *, expired: bool) -> list[dict]:
    branches = scoped_branch_ids(request.user)
    today = timezone.localdate()

    balances = StockBalance.objects.select_related("branch", "medicine", "batch").filter(
        batch__expiry_date__isnull=False
    )
    if branches is not None:
        balances = balances.filter(branch_id__in=branches)
    if request.query_params.get("branch"):
        balances = balances.filter(branch_id=request.query_params["branch"])

    if expired:
        balances = balances.filter(batch__expiry_date__lt=today).exclude(
            batch__status=BatchStatus.RECALLED
        )
    else:
        balances = balances.filter(
            batch__expiry_date__gte=today,
            batch__expiry_date__lte=today + timedelta(days=MAX_NEAR_EXPIRY_SCAN_DAYS),
        ).exclude(batch__status__in=[BatchStatus.RECALLED, BatchStatus.DAMAGED])

    days_param = request.query_params.get("days")
    global_days = int(days_param) if days_param and days_param.isdigit() else None

    rows = []
    for balance in balances:
        if balance.qty_on_hand <= 0 and balance.qty_quarantine <= 0:
            continue
        days = (balance.batch.expiry_date - today).days
        threshold = global_days or balance.medicine.near_expiry_days or DEFAULT_NEAR_EXPIRY_DAYS
        if not expired and days > threshold:
            continue
        rows.append(
            {
                "branch_name": balance.branch.name,
                "medicine_name": balance.medicine.name,
                "medicine_code": balance.medicine.code,
                "batch_number": balance.batch.batch_number,
                "expiry_date": balance.batch.expiry_date,
                "days_to_expiry": days,
                "qty_on_hand": balance.qty_on_hand,
                "qty_quarantine": balance.qty_quarantine,
                "value_on_hand": (balance.qty_on_hand * balance.batch.unit_cost).quantize(
                    Decimal("0.01")
                ),
                "status": balance.batch.status,
            }
        )
    rows.sort(key=lambda row: row["days_to_expiry"])
    return rows


class NearExpiryReportView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        rows = _batch_report_rows(request, expired=False)
        return Response({"count": len(rows), "results": rows})


class ExpiredReportView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        rows = _batch_report_rows(request, expired=True)
        return Response({"count": len(rows), "results": rows})


class LedgerIntegrityView(APIView):
    """Ad-hoc reconciliation view: cached balances vs ledger sums."""

    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        qs = StockBalance.objects.select_related("branch", "medicine", "batch")
        branches = scoped_branch_ids(request.user)
        if branches is not None:
            qs = qs.filter(branch_id__in=branches)

        mismatches = []
        for balance in qs:
            totals = ledger_quantities(balance.branch, balance.medicine, balance.batch)
            if (
                totals["SALEABLE"] != balance.qty_on_hand
                or totals["PROMO"] != balance.qty_promo
                or totals["QUARANTINE"] != balance.qty_quarantine
            ):
                mismatches.append(
                    {
                        "branch_name": balance.branch.name,
                        "medicine_code": balance.medicine.code,
                        "batch_number": balance.batch.batch_number,
                        "cached": {
                            "saleable": balance.qty_on_hand,
                            "promo": balance.qty_promo,
                            "quarantine": balance.qty_quarantine,
                        },
                        "ledger": totals,
                    }
                )
        return Response(
            {
                "consistent": len(mismatches) == 0,
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
            }
        )


class StockTransferViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["STOCK_VIEW"],
        "retrieve": ["STOCK_VIEW"],
        "create": ["STOCK_TRANSFER"],
        "confirm": ["STOCK_TRANSFER"],
    }
    permission_classes = [HasPermission]
    serializer_class = StockTransferReadSerializer
    queryset = (
        StockTransfer.objects.select_related(
            "from_branch", "to_branch", "requested_by", "confirmed_by"
        ).prefetch_related("items__medicine", "items__batch")
    )
    filterset_fields = ["status", "from_branch", "to_branch"]
    search_fields = ["number", "notes", "items__medicine__name"]
    ordering = ["-business_date", "-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        branches = scoped_branch_ids(self.request.user)
        if branches is not None:
            qs = qs.filter(
                Q(from_branch_id__in=branches) | Q(to_branch_id__in=branches)
            )
        return qs

    def create(self, request):
        serializer = StockTransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.branches.models import Branch
        from apps.catalog.models import MedicineBatch

        from_branch = Branch.objects.filter(id=data["from_branch"]).first()
        to_branch = Branch.objects.filter(id=data["to_branch"]).first()
        if from_branch is None or to_branch is None:
            raise APIError("INVALID_BRANCH", "Source or destination branch not found.")

        user = request.user
        if not (user.is_superuser or user.has_all_branch_scope):
            if str(from_branch.id) not in {str(b) for b in user.branch_ids}:
                raise APIError(
                    "BRANCH_SCOPE_EXCEEDED",
                    "You cannot transfer stock out of a branch outside your scope.",
                    status_code=403,
                )

        items_data = []
        for row in data["items"]:
            batch = (
                MedicineBatch.objects.select_related("medicine")
                .filter(id=row["batch"])
                .first()
            )
            if batch is None:
                raise APIError("INVALID_BATCH", "Batch not found.")
            if str(batch.medicine_id) != str(row["medicine"]):
                raise APIError("INVALID_BATCH", "Batch does not belong to the selected medicine.")
            items_data.append({**row, "batch": batch, "medicine": batch.medicine})

        transfer = create_stock_transfer(
            from_branch=from_branch,
            to_branch=to_branch,
            business_date=data.get("business_date"),
            notes=data.get("notes", ""),
            items_data=items_data,
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="STOCK_TRANSFER_CREATED",
            entity_type="stock_transfer",
            entity_id=transfer.id,
            after={
                "from_branch": str(transfer.from_branch_id),
                "to_branch": str(transfer.to_branch_id),
                "lines": len(items_data),
            },
            branch=transfer.from_branch,
            request=request,
        )
        return Response(
            StockTransferReadSerializer(transfer).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        transfer = confirm_stock_transfer(transfer=self.get_object(), actor=request.user)
        log_action(
            actor=request.user,
            action="STOCK_TRANSFER_CONFIRMED",
            entity_type="stock_transfer",
            entity_id=transfer.id,
            after={"number": transfer.number or ""},
            branch=transfer.from_branch,
            request=request,
        )
        return Response(StockTransferReadSerializer(transfer).data)


class StockAdjustmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [HasPermission]
    serializer_class = StockAdjustmentReadSerializer
    queryset = StockAdjustment.objects.select_related("branch", "requested_by", "approved_by").prefetch_related(
        "items__medicine", "items__batch"
    )
    filterset_fields = ["branch", "status", "adjustment_type", "reason_code"]
    search_fields = ["number", "notes", "items__medicine__name"]
    ordering = ["-business_date", "-created_at"]

    def get_permissions(self):
        return [HasPermission()]

    @property
    def required_permissions(self):
        if self.action in ("list", "retrieve"):
            return ["STOCK_VIEW"]
        return ["STOCK_ADJUST"]

    def get_queryset(self):
        qs = super().get_queryset()
        branches = scoped_branch_ids(self.request.user)
        if branches is not None:
            qs = qs.filter(branch_id__in=branches)
        return qs

    def create(self, request):
        serializer = StockAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.branches.models import Branch
        from apps.catalog.models import MedicineBatch

        branch = Branch.objects.filter(id=data["branch"]).first()
        if branch is None:
            raise APIError("INVALID_BRANCH", "Branch not found.")

        items_data = []
        for row in data["items"]:
            batch = (
                MedicineBatch.objects.select_related("medicine")
                .filter(id=row["batch"])
                .first()
            )
            if batch is None:
                raise APIError("INVALID_BATCH", "Batch not found.")
            if str(batch.medicine_id) != str(row["medicine"]):
                raise APIError("INVALID_BATCH", "Batch does not belong to the selected medicine.")
            items_data.append({**row, "batch": batch, "medicine": batch.medicine})

        adjustment = create_stock_adjustment(
            branch=branch,
            adjustment_type=data["adjustment_type"],
            reason_code=data["reason_code"],
            business_date=data.get("business_date"),
            notes=data.get("notes", ""),
            items_data=items_data,
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="STOCK_ADJUSTMENT_CREATED",
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            after={"number": adjustment.number or "", "type": adjustment.adjustment_type, "total_value": str(adjustment.total_value), "status": adjustment.status},
            branch=adjustment.branch,
            request=request,
        )
        return Response(
            StockAdjustmentReadSerializer(adjustment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        adjustment = approve_stock_adjustment(
            adjustment=self.get_object(),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="STOCK_ADJUSTMENT_APPROVED",
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            after={"number": adjustment.number or "", "total_value": str(adjustment.total_value)},
            branch=adjustment.branch,
            request=request,
        )
        return Response(StockAdjustmentReadSerializer(adjustment).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        adjustment = reject_stock_adjustment(
            adjustment=self.get_object(), actor=request.user, reason=request.data.get("reason", "")
        )
        log_action(
            actor=request.user,
            action="STOCK_ADJUSTMENT_REJECTED",
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            after={"number": adjustment.number or "", "reason": request.data.get("reason", "")},
            branch=adjustment.branch,
            request=request,
        )
        return Response(StockAdjustmentReadSerializer(adjustment).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        adjustment = reverse_stock_adjustment(
            adjustment=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="STOCK_ADJUSTMENT_REVERSED",
            entity_type="stock_adjustment",
            entity_id=adjustment.id,
            after={"number": adjustment.number or "", "reason": request.data.get("reason", "")},
            branch=adjustment.branch,
            request=request,
        )
        return Response(StockAdjustmentReadSerializer(adjustment).data)
