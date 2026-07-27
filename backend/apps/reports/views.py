"""Financial reports: P&L, inventory valuation and position snapshot.

All figures derive from document tables and append-only ledgers; the P&L also
returns a reconciliation block proving revenue/COGS trace back to source rows.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import Expense, FinancialAccount, Income
from apps.common.permissions import HasPermission
from apps.inventory.models import EntryType, InventoryTransaction, StockBalance
from apps.payments.models import Payment, PaymentStatus
from apps.sales.models import (
    CustomerLedgerEntry,
    SalesInvoice,
    SalesInvoiceStatus,
    SalesReturn,
    SalesReturnDocStatus,
)
from apps.suppliers.models import SupplierLedgerEntry

TWO = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def pct(delta: Decimal, base: Decimal) -> Decimal | None:
    if base == 0:
        return None
    return ((delta / abs(base)) * 100).quantize(Decimal("0.01"))


def branch_scoped(user, queryset, field: str = "branch_id"):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(**{f"{field}__in": user.branch_ids})


def resolve_period(request) -> tuple[date, date]:
    today = timezone.localdate()
    raw_from = request.query_params.get("date_from")
    raw_to = request.query_params.get("date_to")
    date_to = date.fromisoformat(raw_to) if raw_to else today
    date_from = date.fromisoformat(raw_from) if raw_from else date_to.replace(day=1)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _sum(queryset, expression, output_field):
    return queryset.aggregate(
        total=Sum(ExpressionWrapper(expression, output_field=output_field))
    )["total"] or Decimal("0")


def compute_pl(user, date_from: date, date_to: date) -> dict:
    money_field = DecimalField(max_digits=18, decimal_places=2)

    invoices = branch_scoped(
        user,
        SalesInvoice.objects.filter(
            lifecycle=SalesInvoiceStatus.CONFIRMED, business_date__range=(date_from, date_to)
        ),
    )
    returns = branch_scoped(
        user,
        SalesReturn.objects.filter(
            status=SalesReturnDocStatus.CONFIRMED, business_date__range=(date_from, date_to)
        ),
    )

    sales_net = _sum(
        invoices,
        F("subtotal") - F("discount_total"),
        money_field,
    )
    returns_net = _sum(
        returns,
        F("subtotal") - F("discount_reversal"),
        money_field,
    )
    net_revenue = money(sales_net - returns_net)

    movements = branch_scoped(
        user,
        InventoryTransaction.objects.filter(business_date__range=(date_from, date_to)),
    )

    def movement_value(filters: Q) -> Decimal:
        return money(movements.filter(filters).aggregate(total=Sum("value_delta"))["total"] or 0)

    sale_value = movement_value(Q(entry_type=EntryType.SALE))
    return_value = movement_value(Q(entry_type=EntryType.SALES_RETURN))
    cancel_value = movement_value(
        Q(entry_type=EntryType.REVERSAL, source_type="SALES_CANCEL")
    )
    cogs = money(-(sale_value + return_value + cancel_value))
    gross_profit = money(net_revenue - cogs)

    damage_loss = money(-movement_value(Q(entry_type=EntryType.DAMAGE)))
    expiry_loss = money(-movement_value(Q(entry_type=EntryType.EXPIRY)))
    adjustments_net = money(-movement_value(Q(entry_type=EntryType.ADJUSTMENT)))
    adjustment_reversals = money(
        -movement_value(
            Q(entry_type=EntryType.REVERSAL, source_type="STOCK_ADJUSTMENT_REVERSAL")
        )
    )
    total_losses = money(damage_loss + expiry_loss + adjustments_net + adjustment_reversals)

    expenses = branch_scoped(
        user,
        Expense.objects.filter(status="POSTED", business_date__range=(date_from, date_to)),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    incomes = branch_scoped(
        user,
        Income.objects.filter(status="POSTED", business_date__range=(date_from, date_to)),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    net_profit = money(gross_profit - total_losses - expenses + incomes)

    # Reconciliation: customer ledger movement in the period
    ledger_delta = branch_scoped(
        user,
        CustomerLedgerEntry.objects.filter(business_date__range=(date_from, date_to)),
    ).aggregate(total=Sum("amount_delta"))["total"] or Decimal("0")
    receipts = branch_scoped(
        user,
        Payment.objects.filter(
            status=PaymentStatus.ACTIVE, business_date__range=(date_from, date_to)
        ),
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return {
        "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        "revenue": {
            "sales_net": str(money(sales_net)),
            "returns_net": str(money(returns_net)),
            "net_revenue": str(net_revenue),
        },
        "cogs": str(cogs),
        "gross_profit": str(gross_profit),
        "gross_margin_pct": str(pct(gross_profit, net_revenue)) if net_revenue else None,
        "losses": {
            "damage": str(damage_loss),
            "expiry": str(expiry_loss),
            "adjustments_net": str(adjustments_net),
            "adjustment_reversals": str(adjustment_reversals),
            "total": str(total_losses),
        },
        "expenses": str(money(expenses)),
        "other_income": str(money(incomes)),
        "net_profit": str(net_profit),
        "reconciliation": {
            "customer_ledger_delta": str(money(ledger_delta)),
            "receipts": str(money(receipts)),
            "note": (
                "customer_ledger_delta should equal net revenue - receipts - returns credit "
                "for the period"
            ),
        },
    }


class ProfitLossReportView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW_COST"]

    def get(self, request):
        date_from, date_to = resolve_period(request)
        current = compute_pl(request.user, date_from, date_to)

        length = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=length - 1)
        previous = compute_pl(request.user, previous_from, previous_to)

        current_revenue = Decimal(current["revenue"]["net_revenue"])
        previous_revenue = Decimal(previous["revenue"]["net_revenue"])
        current_profit = Decimal(current["net_profit"])
        previous_profit = Decimal(previous["net_profit"])

        return Response(
            {
                "current": current,
                "previous": previous,
                "comparison": {
                    "revenue_delta": str(money(current_revenue - previous_revenue)),
                    "revenue_delta_pct": str(pct(current_revenue - previous_revenue, previous_revenue))
                    if previous_revenue
                    else None,
                    "net_profit_delta": str(money(current_profit - previous_profit)),
                    "net_profit_delta_pct": str(pct(current_profit - previous_profit, previous_profit))
                    if previous_profit
                    else None,
                },
            }
        )


class InventoryValuationView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW_COST"]

    def get(self, request):
        balances = branch_scoped(
            request.user,
            StockBalance.objects.select_related("branch", "medicine", "batch"),
        )
        if request.query_params.get("branch"):
            balances = balances.filter(branch_id=request.query_params["branch"])

        per_branch: dict[str, dict] = {}
        for balance in balances:
            value_saleable = (balance.qty_on_hand * balance.batch.unit_cost).quantize(TWO)
            value_quarantine = (balance.qty_quarantine * balance.batch.unit_cost).quantize(TWO)
            value_promo = (balance.qty_promo * balance.batch.unit_cost).quantize(TWO)
            row = per_branch.setdefault(
                str(balance.branch_id),
                {
                    "branch": balance.branch_id,
                    "branch_name": balance.branch.name,
                    "saleable_qty": Decimal("0"),
                    "saleable_value": Decimal("0"),
                    "quarantine_qty": Decimal("0"),
                    "quarantine_value": Decimal("0"),
                    "promo_qty": Decimal("0"),
                    "promo_value": Decimal("0"),
                },
            )
            row["saleable_qty"] += balance.qty_on_hand
            row["saleable_value"] += value_saleable
            row["quarantine_qty"] += balance.qty_quarantine
            row["quarantine_value"] += value_quarantine
            row["promo_qty"] += balance.qty_promo
            row["promo_value"] += value_promo

        def as_strings(row: dict) -> dict:
            return {key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()}

        results = [as_strings(row) for row in per_branch.values()]
        total_value = sum((Decimal(row["saleable_value"]) + Decimal(row["quarantine_value"]) + Decimal(row["promo_value"]) for row in results), Decimal("0"))

        return Response(
            {
                "count": len(results),
                "total_value": str(money(total_value)),
                "results": sorted(results, key=lambda row: row["branch_name"]),
            }
        )


class FinancialPositionView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        user = request.user

        receivables = branch_scoped(user, CustomerLedgerEntry.objects.all()).aggregate(
            total=Sum("amount_delta")
        )["total"] or Decimal("0")
        payables = branch_scoped(user, SupplierLedgerEntry.objects.all()).aggregate(
            total=Sum("amount_delta")
        )["total"] or Decimal("0")

        accounts = FinancialAccount.objects.filter(is_active=True)
        if not (user.is_superuser or user.has_all_branch_scope):
            accounts = accounts.filter(
                Q(branch_id__in=user.branch_ids) | Q(branch__isnull=True)
            )
        cash_position = accounts.aggregate(total=Sum("balance_cache"))["total"] or Decimal("0")
        by_account = [
            {
                "account": account.id,
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "balance": str(account.balance_cache),
            }
            for account in accounts.order_by("name")
        ]

        balances = branch_scoped(user, StockBalance.objects.select_related("batch"))
        stock_value = sum(
            (balance.qty_on_hand * balance.batch.unit_cost for balance in balances),
            Decimal("0"),
        )
        quarantine_value = sum(
            (balance.qty_quarantine * balance.batch.unit_cost for balance in balances),
            Decimal("0"),
        )

        return Response(
            {
                "receivables": str(money(receivables)),
                "payables": str(money(payables)),
                "cash_position": str(money(cash_position)),
                "accounts": by_account,
                "stock_value_saleable": str(money(stock_value)),
                "stock_value_quarantine": str(money(quarantine_value)),
                "net_working_position": str(
                    money(Decimal(receivables) - Decimal(payables) + Decimal(cash_position) + stock_value)
                ),
            }
        )


class SalesAttributionView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]
    group_field = ""

    def get(self, request):
        from django.db.models import Count

        money_field = DecimalField(max_digits=18, decimal_places=2)
        date_from, date_to = resolve_period(request)

        invoices = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED, business_date__range=(date_from, date_to)
            ),
        )
        filter_value = request.query_params.get(self.group_field)
        if filter_value:
            invoices = invoices.filter(**{f"{self.group_field}_id": filter_value})

        rows = (
            invoices.values(f"{self.group_field}_id", f"{self.group_field}__name")
            .annotate(
                net=Sum(
                    ExpressionWrapper(
                        F("subtotal") - F("discount_total"), output_field=money_field
                    )
                ),
                count=Count("id"),
            )
            .order_by(f"{self.group_field}__name")
        )
        results = [
            {
                "id": row[f"{self.group_field}_id"],
                "name": row[f"{self.group_field}__name"] or "Unassigned",
                "net_revenue": str(money(row["net"])),
                "invoice_count": row["count"],
            }
            for row in rows
        ]
        total = sum((Decimal(row["net_revenue"]) for row in results), Decimal("0"))
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(results),
                "total_net_revenue": str(money(total)),
                "results": results,
            }
        )


class SalesByDoctorView(SalesAttributionView):
    group_field = "doctor"


class SalesByRepView(SalesAttributionView):
    group_field = "sales_rep"


def csv_response(filename: str, headers: list[str], rows: list[list]):
    import csv
    import io

    from django.http import HttpResponse

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def user_has_cost_access(user) -> bool:
    return bool(user.is_superuser or "REPORT_VIEW_COST" in user.effective_permission_codes)


class SalesSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        date_from, date_to = resolve_period(request)
        invoices = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED, business_date__range=(date_from, date_to)
            ),
        )
        rows_map: dict[str, dict] = {}
        for row in invoices.values("business_date", "subtotal", "discount_total", "vat_total", "grand_total"):
            entry = rows_map.setdefault(
                row["business_date"].isoformat(),
                {"invoices": 0, "net": Decimal("0"), "vat": Decimal("0"), "grand": Decimal("0")},
            )
            entry["invoices"] += 1
            entry["net"] += row["subtotal"] - row["discount_total"]
            entry["vat"] += row["vat_total"]
            entry["grand"] += row["grand_total"]

        results = [
            {
                "date": date_key,
                "invoices": row["invoices"],
                "net_revenue": str(money(row["net"])),
                "vat": str(money(row["vat"])),
                "grand_total": str(money(row["grand"])),
            }
            for date_key, row in sorted(rows_map.items())
        ]
        totals = {
            "invoices": sum((row["invoices"] for row in results), 0),
            "net_revenue": str(money(sum((Decimal(row["net_revenue"]) for row in results), Decimal("0")))),
            "vat": str(money(sum((Decimal(row["vat"]) for row in results), Decimal("0")))),
            "grand_total": str(money(sum((Decimal(row["grand_total"]) for row in results), Decimal("0")))),
        }
        if request.query_params.get("export") == "csv":
            return csv_response(
                "sales-summary.csv",
                ["date", "invoices", "net_revenue", "vat", "grand_total"],
                [[row["date"], row["invoices"], row["net_revenue"], row["vat"], row["grand_total"]] for row in results],
            )
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(results),
                "totals": totals,
                "results": results,
            }
        )


class PurchasesSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        from apps.purchases.models import Purchase, PurchaseStatus

        date_from, date_to = resolve_period(request)
        purchases = branch_scoped(
            request.user,
            Purchase.objects.filter(
                lifecycle=PurchaseStatus.CONFIRMED, business_date__range=(date_from, date_to)
            ),
        )
        rows_map: dict[str, dict] = {}
        for row in purchases.values("business_date", "subtotal", "discount_total", "vat_total", "grand_total"):
            entry = rows_map.setdefault(
                row["business_date"].isoformat(),
                {"purchases": 0, "net": Decimal("0"), "vat": Decimal("0"), "grand": Decimal("0")},
            )
            entry["purchases"] += 1
            entry["net"] += row["subtotal"] - row["discount_total"]
            entry["vat"] += row["vat_total"]
            entry["grand"] += row["grand_total"]

        results = [
            {
                "date": date_key,
                "purchases": row["purchases"],
                "net_cost": str(money(row["net"])),
                "vat": str(money(row["vat"])),
                "grand_total": str(money(row["grand"])),
            }
            for date_key, row in sorted(rows_map.items())
        ]
        totals = {
            "purchases": sum((row["purchases"] for row in results), 0),
            "net_cost": str(money(sum((Decimal(row["net_cost"]) for row in results), Decimal("0")))),
            "grand_total": str(money(sum((Decimal(row["grand_total"]) for row in results), Decimal("0")))),
        }
        if request.query_params.get("export") == "csv":
            return csv_response(
                "purchases-summary.csv",
                ["date", "purchases", "net_cost", "vat", "grand_total"],
                [[row["date"], row["purchases"], row["net_cost"], row["vat"], row["grand_total"]] for row in results],
            )
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(results),
                "totals": totals,
                "results": results,
            }
        )


class SalesByItemView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        from apps.sales.models import SalesInvoiceItem

        date_from, date_to = resolve_period(request)
        has_cost = user_has_cost_access(request.user)

        items = SalesInvoiceItem.objects.filter(
            invoice__lifecycle=SalesInvoiceStatus.CONFIRMED,
            invoice__business_date__range=(date_from, date_to),
        )
        if not (request.user.is_superuser or request.user.has_all_branch_scope):
            items = items.filter(invoice__branch_id__in=request.user.branch_ids)
        search = request.query_params.get("search")
        if search:
            items = items.filter(medicine__name__icontains=search)

        item_map: dict[str, dict] = {}
        fields = ["medicine_id", "medicine__name", "medicine__code", "qty", "unit_price", "line_discount"]
        cached = items.values(*fields)
        for row in cached:
            entry = item_map.setdefault(
                str(row["medicine_id"]),
                {
                    "medicine": row["medicine_id"],
                    "name": row["medicine__name"],
                    "code": row["medicine__code"],
                    "qty": Decimal("0"),
                    "gross": Decimal("0"),
                    "discount": Decimal("0"),
                    "net": Decimal("0"),
                },
            )
            entry["qty"] += row["qty"]
            entry["gross"] += row["qty"] * row["unit_price"]
            entry["discount"] += row["line_discount"]
            entry["net"] += row["qty"] * row["unit_price"] - row["line_discount"]

        results = []
        for entry in sorted(item_map.values(), key=lambda row: row["net"], reverse=True):
            result = {
                "medicine": entry["medicine"],
                "name": entry["name"],
                "code": entry["code"],
                "qty": str(entry["qty"]),
                "gross": str(money(entry["gross"])),
                "discount": str(money(entry["discount"])),
                "net_revenue": str(money(entry["net"])),
            }
            results.append(result)

        if has_cost:
            cost_map: dict[str, Decimal] = {}
            for row in items.values("medicine_id", "qty", "unit_cost"):
                key = str(row["medicine_id"])
                cost_map[key] = cost_map.get(key, Decimal("0")) + row["qty"] * row["unit_cost"]
            for result in results:
                cost = money(cost_map.get(str(result["medicine"]), Decimal("0")))
                result["cost"] = str(cost)
                result["gross_profit"] = str(money(Decimal(result["net_revenue"]) - cost))

        if request.query_params.get("export") == "csv":
            headers = ["medicine", "code", "qty", "gross", "discount", "net_revenue"]
            if has_cost:
                headers += ["cost", "gross_profit"]
            return csv_response(
                "sales-by-item.csv",
                headers,
                [[row.get(header, "") for header in headers] for row in results],
            )
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(results),
                "has_cost_access": has_cost,
                "results": results,
            }
        )


class SalesByCustomerView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        date_from, date_to = resolve_period(request)
        invoices = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED, business_date__range=(date_from, date_to)
            ),
        )
        search = request.query_params.get("search")
        if search:
            invoices = invoices.filter(customer__name__icontains=search)

        customer_map: dict[str, dict] = {}
        for row in invoices.values(
            "customer_id", "customer__name", "customer__code", "subtotal", "discount_total", "grand_total", "paid_total"
        ):
            entry = customer_map.setdefault(
                str(row["customer_id"]),
                {
                    "customer": row["customer_id"],
                    "name": row["customer__name"],
                    "code": row["customer__code"],
                    "invoices": 0,
                    "net": Decimal("0"),
                    "paid": Decimal("0"),
                    "outstanding": Decimal("0"),
                },
            )
            entry["invoices"] += 1
            entry["net"] += row["subtotal"] - row["discount_total"]
            entry["paid"] += row["paid_total"]
            entry["outstanding"] += row["grand_total"] - row["paid_total"]

        results = []
        for entry in sorted(customer_map.values(), key=lambda row: row["net"], reverse=True):
            results.append(
                {
                    "customer": entry["customer"],
                    "name": entry["name"],
                    "code": entry["code"],
                    "invoices": entry["invoices"],
                    "net_revenue": str(money(entry["net"])),
                    "paid": str(money(entry["paid"])),
                    "outstanding": str(money(entry["outstanding"])),
                }
            )

        if request.query_params.get("export") == "csv":
            return csv_response(
                "sales-by-customer.csv",
                ["customer", "code", "invoices", "net_revenue", "paid", "outstanding"],
                [
                    [row["name"], row["code"], row["invoices"], row["net_revenue"], row["paid"], row["outstanding"]]
                    for row in results
                ],
            )
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(results),
                "results": results,
            }
        )
