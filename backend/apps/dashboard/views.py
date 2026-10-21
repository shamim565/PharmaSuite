from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Max, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FinancialAccount
from apps.accounts.models import Role, User, UserStatus
from apps.branches.models import Branch, BranchStatus
from apps.catalog.models import Medicine
from apps.common.permissions import HasPermission
from apps.common.schema import object_response
from apps.inventory.models import StockBalance
from apps.payments.models import Payment, PaymentStatus
from apps.sales.models import CustomerLedgerEntry, SalesInvoice, SalesInvoiceStatus
from apps.suppliers.models import SupplierLedgerEntry


@object_response
class DashboardSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["DASHBOARD_VIEW"]

    def get(self, request):
        user = request.user
        all_branches = user.is_superuser or user.has_all_branch_scope
        branch_filter = {} if all_branches else {"id__in": user.branch_ids}

        branches = Branch.objects.filter(**branch_filter)
        users = User.objects.all()
        if not all_branches:
            users = users.filter(user_branches__branch_id__in=user.branch_ids).distinct()

        medicines = Medicine.objects.all()

        balances = StockBalance.objects.all()
        if not all_branches:
            balances = balances.filter(branch_id__in=user.branch_ids)

        stock_value = balances.annotate(
            line_value=ExpressionWrapper(
                F("qty_on_hand") * F("batch__unit_cost"),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            )
        ).aggregate(total=Sum("line_value"))["total"] or Decimal("0")

        per_medicine = balances.values("medicine_id").annotate(
            total=Sum("qty_on_hand"), reorder=Max("medicine__reorder_level")
        )
        low_stock_count = sum(
            1
            for row in per_medicine
            if (row["reorder"] or Decimal("0")) > 0
            and (row["total"] or Decimal("0")) <= row["reorder"]
        )

        today = timezone.localdate()
        near_expiry_count = (
            balances.filter(
                batch__expiry_date__gte=today,
                batch__expiry_date__lte=today + timedelta(days=90),
            )
            .exclude(batch__status__in=["RECALLED", "DAMAGED"])
            .filter(qty_on_hand__gt=0)
            .count()
        )

        invoices = SalesInvoice.objects.filter(lifecycle=SalesInvoiceStatus.CONFIRMED)
        receipts = Payment.objects.filter(status=PaymentStatus.ACTIVE)
        payables = SupplierLedgerEntry.objects.all()
        if not all_branches:
            invoices = invoices.filter(branch_id__in=user.branch_ids)
            receipts = receipts.filter(branch_id__in=user.branch_ids)
            payables = payables.filter(branch_id__in=user.branch_ids)

        sales_today = (
            invoices.filter(business_date=today).aggregate(total=Sum("grand_total"))["total"]
            or Decimal("0")
        )
        collections_today = (
            receipts.filter(business_date=today).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        supplier_payable = payables.aggregate(total=Sum("amount_delta"))["total"] or Decimal("0")
        receivables = CustomerLedgerEntry.objects.all()
        if not all_branches:
            receivables = receivables.filter(branch_id__in=user.branch_ids)
        customer_due = receivables.aggregate(total=Sum("amount_delta"))["total"] or Decimal("0")

        account_qs = FinancialAccount.objects.filter(is_active=True)
        if not all_branches:
            from django.db.models import Q

            account_qs = account_qs.filter(
                Q(branch_id__in=user.branch_ids) | Q(branch__isnull=True)
            )
        cash_position = (
            account_qs.aggregate(total=Sum("balance_cache"))["total"] or Decimal("0")
        )

        return Response(
            {
                "generated_at": timezone.now(),
                "branch_scope": "ALL" if all_branches else "ASSIGNED",
                "users": {
                    "total": users.count(),
                    "active": users.filter(status=UserStatus.ACTIVE).count(),
                },
                "branches": {
                    "total": branches.count(),
                    "active": branches.filter(status=BranchStatus.ACTIVE).count(),
                },
                "roles": {"total": Role.objects.count()},
                "medicines": {
                    "total": medicines.count(),
                    "active": medicines.filter(is_active=True).count(),
                },
                "operations": {
                    "sales_today": sales_today,
                    "collections_today": collections_today,
                    "customer_due": customer_due,
                    "supplier_payable": supplier_payable,
                    "cash_position": cash_position,
                    "stock_value": stock_value,
                    "low_stock_count": low_stock_count,
                    "near_expiry_count": near_expiry_count,
                },
            }
        )


@object_response
class DashboardWidgetsView(APIView):
    """Trend and top-N widgets plus alert previews for the dashboard.

    Aggregation is performed in Python over value rows (small result sets)
    to stay independent of ORM aggregate-expression edge cases.
    """

    permission_classes = [HasPermission]
    required_permissions = ["DASHBOARD_VIEW"]

    def get(self, request):
        from apps.inventory.views import _summary_rows

        user = request.user
        all_branches = user.is_superuser or user.has_all_branch_scope
        today = timezone.localdate()
        days_param = request.query_params.get("days", "30")
        days = max(7, min(int(days_param) if days_param.isdigit() else 30, 90))
        start = today - timedelta(days=days - 1)

        invoices = SalesInvoice.objects.filter(
            lifecycle=SalesInvoiceStatus.CONFIRMED, business_date__range=(start, today)
        )
        if not all_branches:
            invoices = invoices.filter(branch_id__in=user.branch_ids)

        trend_map: dict[str, dict] = {}
        customer_map: dict[str, dict] = {}
        for row in invoices.values(
            "business_date",
            "subtotal",
            "discount_total",
            "customer_id",
            "customer__name",
        ):
            date_key = row["business_date"].isoformat()
            net = row["subtotal"] - row["discount_total"]
            entry = trend_map.setdefault(date_key, {"revenue": Decimal("0"), "invoices": 0})
            entry["revenue"] += net
            entry["invoices"] += 1

            customer = customer_map.setdefault(
                str(row["customer_id"]),
                {
                    "customer": row["customer_id"],
                    "name": row["customer__name"],
                    "revenue": Decimal("0"),
                    "invoices": 0,
                },
            )
            customer["revenue"] += net
            customer["invoices"] += 1

        sales_trend = [
            {"date": date_key, "revenue": str(row["revenue"]), "invoices": row["invoices"]}
            for date_key, row in sorted(trend_map.items())
        ]
        top_customers = [
            {
                "customer": row["customer"],
                "name": row["name"],
                "revenue": str(row["revenue"]),
                "invoices": row["invoices"],
            }
            for row in sorted(customer_map.values(), key=lambda row: row["revenue"], reverse=True)[:5]
        ]

        from apps.sales.models import SalesInvoiceItem

        item_map: dict[str, dict] = {}
        items = SalesInvoiceItem.objects.filter(invoice__in=invoices).values(
            "medicine_id", "medicine__name", "medicine__code", "qty", "unit_price", "line_discount"
        )
        for row in items:
            medicine = item_map.setdefault(
                str(row["medicine_id"]),
                {
                    "medicine": row["medicine_id"],
                    "name": row["medicine__name"],
                    "code": row["medicine__code"],
                    "qty": Decimal("0"),
                    "revenue": Decimal("0"),
                },
            )
            medicine["qty"] += row["qty"]
            medicine["revenue"] += row["qty"] * row["unit_price"] - row["line_discount"]
        top_items = [
            {
                "medicine": row["medicine"],
                "name": row["name"],
                "code": row["code"],
                "qty": str(row["qty"]),
                "revenue": str(row["revenue"].quantize(Decimal("0.01"))),
            }
            for row in sorted(item_map.values(), key=lambda row: row["revenue"], reverse=True)[:5]
        ]

        low_stock = [row for row in _summary_rows(request) if row["reorder_level"] > 0 and row["is_low_stock"]]
        low_stock = sorted(low_stock, key=lambda row: Decimal(row["qty_on_hand"]))[:5]
        low_stock_payload = [
            {
                "medicine": str(row["medicine"]),
                "name": row["medicine_name"],
                "code": row["medicine_code"],
                "on_hand": str(row["qty_on_hand"]),
                "reorder_level": str(row["reorder_level"]),
            }
            for row in low_stock
        ]

        balances = StockBalance.objects.select_related("batch", "medicine").filter(
            batch__expiry_date__gte=today,
            batch__expiry_date__lte=today + timedelta(days=90),
            qty_on_hand__gt=0,
        )
        if not all_branches:
            balances = balances.filter(branch_id__in=user.branch_ids)
        balances = balances.order_by("batch__expiry_date")[:5]
        near_expiry = [
            {
                "medicine": balance.medicine.name,
                "batch_number": balance.batch.batch_number,
                "expiry_date": balance.batch.expiry_date.isoformat(),
                "days_to_expiry": (balance.batch.expiry_date - today).days,
                "qty_on_hand": str(balance.qty_on_hand),
            }
            for balance in balances
        ]

        return Response(
            {
                "period": {"date_from": start.isoformat(), "date_to": today.isoformat(), "days": days},
                "sales_trend": sales_trend,
                "top_items": top_items,
                "top_customers": top_customers,
                "low_stock": low_stock_payload,
                "near_expiry": near_expiry,
                "medicine_count": Medicine.objects.filter(is_active=True).count(),
            }
        )