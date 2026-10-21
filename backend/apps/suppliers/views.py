from decimal import Decimal

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_action
from apps.common.permissions import HasPermission
from apps.common.schema import object_response
from apps.common.viewsets import PermissionMappedMixin
from apps.suppliers.models import Supplier
from apps.suppliers.serializers import SupplierLedgerEntrySerializer, SupplierSerializer


class SupplierViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["SUPPLIER_VIEW"],
        "retrieve": ["SUPPLIER_VIEW"],
        "create": ["SUPPLIER_MANAGE"],
        "update": ["SUPPLIER_MANAGE"],
        "partial_update": ["SUPPLIER_MANAGE"],
        "ledger": ["SUPPLIER_VIEW"],
        "statement": ["SUPPLIER_VIEW"],
    }
    permission_classes = [HasPermission]
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.all()
    filterset_fields = ["is_active", "supplier_type"]
    search_fields = ["code", "name", "phone", "bin"]
    ordering_fields = ["name", "code", "balance_cache", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        from django.http import HttpResponse

        supplier = self.get_object()
        entries = list(
            supplier.ledger_entries.order_by("created_at", "id")
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
        response["Content-Disposition"] = f'attachment; filename="{supplier.code}-statement.csv"'
        import csv

        writer = csv.DictWriter(
            response, fieldnames=["date", "number", "description", "amount", "balance"]
        )
        writer.writeheader()
        writer.writerows(rows)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        supplier = self.get_object()
        log_action(
            actor=request.user,
            action="SUPPLIER_UPDATED",
            entity_type="supplier",
            entity_id=supplier.id,
            after={"code": supplier.code},
            request=request,
        )
        return response

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        supplier = self.get_object()
        entries = supplier.ledger_entries.select_related("branch").order_by("-created_at", "-id")

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
            row = SupplierLedgerEntrySerializer(entry).data
            row["running_balance"] = balance
            rows.append(row)
        rows.reverse()
        return Response(
            {"balance": str(supplier.balance_cache), "count": len(rows), "results": rows}
        )


@object_response
class PayableSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["SUPPLIER_VIEW"]

    def get(self, request):
        from django.db.models import Sum

        from apps.suppliers.models import SupplierLedgerEntry

        rows = (
            SupplierLedgerEntry.objects.values("supplier_id", "supplier__name", "supplier__code")
            .annotate(balance=Sum("amount_delta"))
            .order_by("supplier__name")
        )
        results = [
            {
                "supplier": row["supplier_id"],
                "supplier_name": row["supplier__name"],
                "supplier_code": row["supplier__code"],
                "balance": str(row["balance"] or Decimal("0")),
            }
            for row in rows
            if (row["balance"] or 0) != 0
        ]
        return Response({"count": len(results), "results": results})
