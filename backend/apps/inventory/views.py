from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_action
from apps.catalog.models import BatchStatus
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.inventory.models import InventoryTransaction, StockAdjustment, StockBalance
from apps.inventory.serializers import (
    InventoryTransactionSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentReadSerializer,
    StockBalanceSerializer,
)
from apps.inventory.services import (
    approve_stock_adjustment,
    create_stock_adjustment,
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


class InventoryTransactionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]
    serializer_class = InventoryTransactionSerializer
    queryset = InventoryTransaction.objects.select_related(
        "branch", "medicine", "batch", "created_by"
    )
    filterset_fields = ["branch", "medicine", "batch", "entry_type", "pool", "transaction_group_id"]
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


def _summary_rows(request) -> list[dict]:
    qs = StockBalance.objects.all()
    branches = scoped_branch_ids(request.user)
    if branches is not None:
        qs = qs.filter(branch_id__in=branches)
    if request.query_params.get("branch"):
        qs = qs.filter(branch_id=request.query_params["branch"])

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
            qty_on_hand=Sum("qty_on_hand"),
            qty_promo=Sum("qty_promo"),
            qty_quarantine=Sum("qty_quarantine"),
        )
        .order_by("medicine__name")
    )

    search = (request.query_params.get("search") or "").lower()
    low_only = request.query_params.get("low_stock") == "true"
    results = []
    for row in aggregated:
        total = row["qty_on_hand"] or Decimal("0")
        reorder = row["medicine__reorder_level"] or Decimal("0")
        is_low = reorder > 0 and total <= reorder
        if search and search not in (row["medicine__name"] or "").lower() and search not in (
            row["medicine__code"] or ""
        ).lower():
            continue
        if low_only and not is_low:
            continue
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
                "is_low_stock": is_low,
                "is_out_of_stock": total <= 0,
            }
        )
    return results


class StockSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        rows = _summary_rows(request)
        return Response({"count": len(rows), "results": rows})


class LowStockReportView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["STOCK_VIEW"]

    def get(self, request):
        rows = [row for row in _summary_rows(request) if row["reorder_level"] > 0 and row["is_low_stock"]]
        return Response({"count": len(rows), "results": rows})


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
