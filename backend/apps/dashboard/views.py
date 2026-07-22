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
from apps.inventory.models import StockBalance
from apps.payments.models import Payment, PaymentStatus
from apps.sales.models import CustomerLedgerEntry, SalesInvoice, SalesInvoiceStatus
from apps.suppliers.models import SupplierLedgerEntry


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
