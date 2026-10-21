"""Advanced Business Intelligence Reports.

Provides:
  - Inventory DSI / Dead Stock / Slow Mover
  - Margin analysis by category / generic
  - Rep performance (target vs actual)
  - Collection efficiency KPI
  - Supplier concentration risk
  - Exception / override audit report
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasPermission
from apps.common.schema import object_response
from apps.inventory.models import StockBalance
from apps.reports.views import (
    branch_scoped,
    csv_response,
    money,
    resolve_period,
    user_has_cost_access,
)
from apps.sales.models import SalesInvoice, SalesInvoiceItem, SalesInvoiceStatus

TWO = Decimal("0.01")
ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# 3.1  Inventory DSI / Dead Stock / Slow Mover
# ---------------------------------------------------------------------------

@object_response
class InventoryDSIView(APIView):
    """
    Days Sales Inventory (DSI) per medicine.
    DSI = (qty_on_hand / avg_daily_sales) — lower is better.

    Also flags:
      - dead_stock: no sales in the last `dead_days` days (default 90)
      - slow_mover: DSI > `slow_dsi` threshold (default 60)
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        today = timezone.localdate()
        dead_days = int(request.query_params.get("dead_days", 90))
        slow_dsi = int(request.query_params.get("slow_dsi", 60))
        search = request.query_params.get("search", "")

        # Period for average sales = last 90 days
        period_days = int(request.query_params.get("avg_days", 90))
        avg_from = today - timedelta(days=period_days)

        # Get all on-hand stock, group by medicine
        balances_qs = branch_scoped(
            request.user,
            StockBalance.objects.filter(qty_on_hand__gt=0)
            .select_related("medicine", "branch"),
        )
        if search:
            balances_qs = balances_qs.filter(medicine__name__icontains=search)

        # Aggregate on-hand by medicine
        stock_map: dict[str, dict] = {}
        for b in balances_qs.values("medicine_id", "medicine__name", "medicine__code",
                                     "medicine__reorder_level", "qty_on_hand"):
            mid = str(b["medicine_id"])
            if mid not in stock_map:
                stock_map[mid] = {
                    "medicine": b["medicine_id"],
                    "name": b["medicine__name"],
                    "code": b["medicine__code"],
                    "reorder_level": b["medicine__reorder_level"],
                    "qty_on_hand": Decimal("0"),
                }
            stock_map[mid]["qty_on_hand"] += b["qty_on_hand"]

        if not stock_map:
            return Response({"count": 0, "results": []})

        # Get sales qty in avg_period
        sales_qs = SalesInvoiceItem.objects.filter(
            invoice__lifecycle=SalesInvoiceStatus.CONFIRMED,
            invoice__business_date__range=(avg_from, today),
            medicine_id__in=list(stock_map.keys()),
        )
        if not (request.user.is_superuser or request.user.has_all_branch_scope):
            sales_qs = sales_qs.filter(invoice__branch_id__in=request.user.branch_ids)

        sales_by_med = {}
        for row in sales_qs.values("medicine_id").annotate(total_qty=Sum("qty")):
            sales_by_med[str(row["medicine_id"])] = row["total_qty"] or ZERO

        # Compute last-sale date per medicine
        last_sale_qs = SalesInvoiceItem.objects.filter(
            invoice__lifecycle=SalesInvoiceStatus.CONFIRMED,
            medicine_id__in=list(stock_map.keys()),
        )
        if not (request.user.is_superuser or request.user.has_all_branch_scope):
            last_sale_qs = last_sale_qs.filter(invoice__branch_id__in=request.user.branch_ids)

        last_sale_by_med = {}
        for row in last_sale_qs.values("medicine_id").annotate(
            last_sale=F("invoice__business_date")
        ).order_by("medicine_id", "-invoice__business_date"):
            mid = str(row["medicine_id"])
            if mid not in last_sale_by_med:
                last_sale_by_med[mid] = row["last_sale"]

        results = []
        for mid, entry in stock_map.items():
            qty_on_hand = entry["qty_on_hand"]
            total_sold = sales_by_med.get(mid, ZERO)
            avg_daily = (total_sold / period_days) if period_days > 0 else ZERO

            dsi = None
            if avg_daily > 0:
                dsi = round(float(qty_on_hand / avg_daily), 1)

            last_sale = last_sale_by_med.get(mid)
            days_since_sale = (today - last_sale).days if last_sale else None

            is_dead = (days_since_sale is None or days_since_sale > dead_days)
            is_slow = (dsi is not None and dsi > slow_dsi)

            results.append({
                "medicine": entry["medicine"],
                "name": entry["name"],
                "code": entry["code"],
                "qty_on_hand": str(qty_on_hand),
                "reorder_level": str(entry["reorder_level"]),
                "avg_daily_sales": str(money(avg_daily)),
                "total_sold_in_period": str(total_sold),
                "dsi": dsi,
                "last_sale_date": last_sale.isoformat() if last_sale else None,
                "days_since_sale": days_since_sale,
                "is_dead_stock": is_dead,
                "is_slow_mover": is_slow,
            })

        # Sort: dead stock first, then slow movers, then by DSI desc
        results.sort(key=lambda r: (not r["is_dead_stock"], not r["is_slow_mover"], r["dsi"] or 9999), reverse=False)

        filter_type = request.query_params.get("filter")  # dead / slow / all
        if filter_type == "dead":
            results = [r for r in results if r["is_dead_stock"]]
        elif filter_type == "slow":
            results = [r for r in results if r["is_slow_mover"]]

        if request.query_params.get("export") == "csv":
            return csv_response(
                "inventory-dsi.csv",
                ["code", "name", "qty_on_hand", "avg_daily_sales", "dsi", "days_since_sale", "is_dead_stock", "is_slow_mover"],
                [[r["code"], r["name"], r["qty_on_hand"], r["avg_daily_sales"],
                  r["dsi"], r["days_since_sale"], r["is_dead_stock"], r["is_slow_mover"]] for r in results],
            )

        return Response({
            "period_days": period_days,
            "dead_days_threshold": dead_days,
            "slow_dsi_threshold": slow_dsi,
            "count": len(results),
            "dead_stock_count": sum(1 for r in results if r["is_dead_stock"]),
            "slow_mover_count": sum(1 for r in results if r["is_slow_mover"]),
            "results": results,
        })


# ---------------------------------------------------------------------------
# 3.2  Margin analysis by category / generic
# ---------------------------------------------------------------------------

@object_response
class MarginAnalysisView(APIView):
    """
    Gross margin (revenue - COGS) grouped by medicine category or generic.
    Requires REPORT_VIEW_COST permission to see cost columns.
    Group by: category (default) or generic (pass ?group_by=generic)
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        date_from, date_to = resolve_period(request)
        has_cost = user_has_cost_access(request.user)
        group_by = request.query_params.get("group_by", "category")  # category | generic

        items_qs = SalesInvoiceItem.objects.filter(
            invoice__lifecycle=SalesInvoiceStatus.CONFIRMED,
            invoice__business_date__range=(date_from, date_to),
        ).select_related("medicine__category", "medicine__generic")

        if not (request.user.is_superuser or request.user.has_all_branch_scope):
            items_qs = items_qs.filter(invoice__branch_id__in=request.user.branch_ids)

        group_map: dict[str, dict] = {}
        for item in items_qs.values(
            "medicine__category_id", "medicine__category__name",
            "medicine__generic_id", "medicine__generic__name",
            "qty", "unit_price", "line_discount", "unit_cost"
        ):
            if group_by == "generic":
                gid = str(item["medicine__generic_id"] or "")
                gname = item["medicine__generic__name"] or "Unclassified"
            else:
                gid = str(item["medicine__category_id"] or "")
                gname = item["medicine__category__name"] or "Unclassified"

            entry = group_map.setdefault(gid, {
                "id": gid,
                "name": gname,
                "qty": ZERO,
                "gross": ZERO,
                "discount": ZERO,
                "net_revenue": ZERO,
                "cogs": ZERO,
            })
            qty = item["qty"] or ZERO
            rev = money(qty * (item["unit_price"] or ZERO))
            disc = item["line_discount"] or ZERO
            net = money(rev - disc)
            cogs = money(qty * (item["unit_cost"] or ZERO)) if has_cost else ZERO

            entry["qty"] += qty
            entry["gross"] += rev
            entry["discount"] += disc
            entry["net_revenue"] += net
            entry["cogs"] += cogs

        results = []
        for entry in sorted(group_map.values(), key=lambda x: x["net_revenue"], reverse=True):
            row = {
                "id": entry["id"],
                "name": entry["name"],
                "qty": str(entry["qty"]),
                "gross": str(money(entry["gross"])),
                "discount": str(money(entry["discount"])),
                "net_revenue": str(money(entry["net_revenue"])),
            }
            if has_cost:
                gp = money(entry["net_revenue"] - entry["cogs"])
                gp_pct = (
                    round(float(gp / entry["net_revenue"] * 100), 2)
                    if entry["net_revenue"] > 0 else 0.0
                )
                row["cogs"] = str(money(entry["cogs"]))
                row["gross_profit"] = str(gp)
                row["gross_profit_pct"] = gp_pct
            results.append(row)

        total_rev = sum((Decimal(r["net_revenue"]) for r in results), ZERO)
        total_gp = sum((Decimal(r.get("gross_profit", "0")) for r in results), ZERO) if has_cost else None

        if request.query_params.get("export") == "csv":
            headers = ["name", "qty", "net_revenue"]
            if has_cost:
                headers += ["cogs", "gross_profit", "gross_profit_pct"]
            return csv_response(
                f"margin-by-{group_by}.csv",
                headers,
                [[r.get(h, "") for h in headers] for r in results],
            )

        return Response({
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "group_by": group_by,
            "has_cost_access": has_cost,
            "total_net_revenue": str(money(total_rev)),
            "total_gross_profit": str(money(total_gp)) if total_gp is not None else None,
            "count": len(results),
            "results": results,
        })


# ---------------------------------------------------------------------------
# 3.3  Rep Performance (Target vs Actual)
# ---------------------------------------------------------------------------

@object_response
class RepPerformanceView(APIView):
    """
    Sales rep performance: actual vs target for a given fiscal year & month.
    Pass ?fiscal_year=2026&period_month=10 (defaults to current month).
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        from apps.representatives.models import Representative, SalesTarget

        today = timezone.localdate()
        fiscal_year = int(request.query_params.get("fiscal_year", today.year))
        period_month = int(request.query_params.get("period_month", today.month))
        rep_filter = request.query_params.get("representative")

        # Actual sales by rep
        invoices_qs = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED,
                business_date__year=fiscal_year,
                business_date__month=period_month,
                sales_rep__isnull=False,
            ),
        )
        if rep_filter:
            invoices_qs = invoices_qs.filter(sales_rep_id=rep_filter)

        actual_by_rep: dict[str, Decimal] = {}
        for row in invoices_qs.values("sales_rep_id").annotate(total=Sum("grand_total")):
            actual_by_rep[str(row["sales_rep_id"])] = row["total"] or ZERO

        # Targets
        targets_qs = SalesTarget.objects.filter(fiscal_year=fiscal_year, period_month=period_month)
        if rep_filter:
            targets_qs = targets_qs.filter(representative_id=rep_filter)
        targets = {
            str(t.representative_id): t
            for t in targets_qs.select_related("representative", "branch")
        }

        # Collect all reps that either have a target or actual sales
        rep_ids = set(actual_by_rep.keys()) | set(targets.keys())
        if rep_filter:
            rep_ids.add(rep_filter)

        reps = {
            str(r.id): r
            for r in Representative.objects.filter(id__in=list(rep_ids)).select_related("branch")
        }

        results = []
        for rid in rep_ids:
            rep = reps.get(rid)
            if not rep:
                continue
            target_obj = targets.get(rid)
            target_amount = target_obj.target_amount if target_obj else ZERO
            actual = actual_by_rep.get(rid, ZERO)
            achievement_pct = (
                round(float(actual / target_amount * 100), 1)
                if target_amount > 0 else None
            )
            results.append({
                "representative": rid,
                "name": rep.name,
                "code": rep.code,
                "rep_type": rep.rep_type,
                "branch": str(rep.branch_id) if rep.branch_id else None,
                "branch_name": rep.branch.name if rep.branch else "",
                "target_amount": str(money(target_amount)),
                "actual_sales": str(money(actual)),
                "achievement_pct": achievement_pct,
                "gap": str(money(target_amount - actual)),
            })

        results.sort(key=lambda r: Decimal(r["actual_sales"]), reverse=True)

        if request.query_params.get("export") == "csv":
            return csv_response(
                "rep-performance.csv",
                ["name", "code", "rep_type", "branch_name", "target_amount", "actual_sales", "achievement_pct", "gap"],
                [[r["name"], r["code"], r["rep_type"], r["branch_name"],
                  r["target_amount"], r["actual_sales"], r["achievement_pct"], r["gap"]] for r in results],
            )

        return Response({
            "fiscal_year": fiscal_year,
            "period_month": period_month,
            "count": len(results),
            "total_target": str(money(sum(Decimal(r["target_amount"]) for r in results))),
            "total_actual": str(money(sum(Decimal(r["actual_sales"]) for r in results))),
            "results": results,
        })


# ---------------------------------------------------------------------------
# 3.4  Collection Efficiency KPI
# ---------------------------------------------------------------------------

@object_response
class CollectionEfficiencyView(APIView):
    """
    Collection efficiency = payments received in period / invoices due in period.
    Returns per-customer breakdown and an aggregate KPI.
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):

        date_from, date_to = resolve_period(request)

        invoices_qs = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED,
                due_date__range=(date_from, date_to),
            ),
        )
        billed: dict[str, dict] = {}
        for row in invoices_qs.values("customer_id", "customer__name", "customer__code",
                                       "grand_total", "paid_total"):
            cid = str(row["customer_id"])
            entry = billed.setdefault(cid, {
                "customer": row["customer_id"],
                "name": row["customer__name"],
                "code": row["customer__code"],
                "invoiced": ZERO,
                "collected": ZERO,
            })
            entry["invoiced"] += row["grand_total"] or ZERO
            entry["collected"] += row["paid_total"] or ZERO

        total_invoiced = sum(e["invoiced"] for e in billed.values())
        total_collected = sum(e["collected"] for e in billed.values())
        total_outstanding = total_invoiced - total_collected
        overall_efficiency = (
            round(float(total_collected / total_invoiced * 100), 2)
            if total_invoiced > 0 else 0.0
        )

        results = []
        for entry in sorted(billed.values(), key=lambda x: x["invoiced"], reverse=True):
            eff = (
                round(float(entry["collected"] / entry["invoiced"] * 100), 1)
                if entry["invoiced"] > 0 else 0.0
            )
            results.append({
                "customer": entry["customer"],
                "name": entry["name"],
                "code": entry["code"],
                "invoiced": str(money(entry["invoiced"])),
                "collected": str(money(entry["collected"])),
                "outstanding": str(money(entry["invoiced"] - entry["collected"])),
                "efficiency_pct": eff,
            })

        if request.query_params.get("export") == "csv":
            return csv_response(
                "collection-efficiency.csv",
                ["name", "code", "invoiced", "collected", "outstanding", "efficiency_pct"],
                [[r["name"], r["code"], r["invoiced"], r["collected"],
                  r["outstanding"], r["efficiency_pct"]] for r in results],
            )

        return Response({
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "kpi": {
                "total_invoiced": str(money(total_invoiced)),
                "total_collected": str(money(total_collected)),
                "total_outstanding": str(money(total_outstanding)),
                "collection_efficiency_pct": overall_efficiency,
            },
            "count": len(results),
            "results": results,
        })


# ---------------------------------------------------------------------------
# 3.5  Supplier Concentration Risk
# ---------------------------------------------------------------------------

@object_response
class SupplierConcentrationView(APIView):
    """
    Purchase spend by supplier with concentration % and cumulative share.
    Flags suppliers that account for >50 % of total spend (high dependency risk).
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        from apps.purchases.models import Purchase, PurchaseStatus

        date_from, date_to = resolve_period(request)

        purchases_qs = branch_scoped(
            request.user,
            Purchase.objects.filter(
                lifecycle=PurchaseStatus.CONFIRMED,
                business_date__range=(date_from, date_to),
            ),
        )

        supplier_map: dict[str, dict] = {}
        for row in purchases_qs.values(
            "supplier_id", "supplier__name", "supplier__code", "grand_total"
        ):
            sid = str(row["supplier_id"])
            entry = supplier_map.setdefault(sid, {
                "supplier": row["supplier_id"],
                "name": row["supplier__name"],
                "code": row["supplier__code"] if hasattr(row, "code") else "",
                "total_spend": ZERO,
                "purchase_count": 0,
            })
            entry["total_spend"] += row["grand_total"] or ZERO
            entry["purchase_count"] += 1

        total_spend = sum(e["total_spend"] for e in supplier_map.values())

        results = []
        cumulative = ZERO
        for entry in sorted(supplier_map.values(), key=lambda x: x["total_spend"], reverse=True):
            pct_share = (
                round(float(entry["total_spend"] / total_spend * 100), 2)
                if total_spend > 0 else 0.0
            )
            cumulative += entry["total_spend"]
            cum_pct = (
                round(float(cumulative / total_spend * 100), 2) if total_spend > 0 else 0.0
            )
            results.append({
                "supplier": entry["supplier"],
                "name": entry["name"],
                "total_spend": str(money(entry["total_spend"])),
                "purchase_count": entry["purchase_count"],
                "pct_of_total": pct_share,
                "cumulative_pct": cum_pct,
                "high_dependency": pct_share >= 30.0,
            })

        if request.query_params.get("export") == "csv":
            return csv_response(
                "supplier-concentration.csv",
                ["name", "total_spend", "purchase_count", "pct_of_total", "cumulative_pct", "high_dependency"],
                [[r["name"], r["total_spend"], r["purchase_count"],
                  r["pct_of_total"], r["cumulative_pct"], r["high_dependency"]] for r in results],
            )

        return Response({
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "total_spend": str(money(total_spend)),
            "supplier_count": len(results),
            "high_dependency_count": sum(1 for r in results if r["high_dependency"]),
            "results": results,
        })


# ---------------------------------------------------------------------------
# 3.6  Exception / Override Report
# ---------------------------------------------------------------------------

@object_response
class ExceptionReportView(APIView):
    """
    Lists all confirmed invoices in the period that had an override:
      - credit override (credit limit bypass)
      - FEFO override (batch selection bypass)
      - Rx override (prescription bypass)
      - zero-value invoice
      - below-cost sale line
    Also shows purchase duplicate overrides.
    """

    permission_classes = [HasPermission]
    required_permissions = ["REPORT_VIEW"]

    def get(self, request):
        date_from, date_to = resolve_period(request)

        invoices_qs = branch_scoped(
            request.user,
            SalesInvoice.objects.filter(
                lifecycle=SalesInvoiceStatus.CONFIRMED,
                business_date__range=(date_from, date_to),
            ).select_related("customer", "branch", "confirmed_by"),
        )

        flagged_ids = set(
            invoices_qs.filter(
                Q(credit_override=True) | Q(fefo_override=True) | Q(rx_override=True)
            ).values_list("id", flat=True)
        )
        flagged_ids |= set(
            invoices_qs.filter(grand_total=0).values_list("id", flat=True)
        )

        below_cost_map: dict[str, list[str]] = {}
        below_cost_items = (
            SalesInvoiceItem.objects.filter(
                invoice__in=invoices_qs,
                is_free_goods=False,
                unit_price__lt=F("unit_cost"),
            )
            .select_related("medicine")
            .values("invoice_id", "medicine__name")
        )
        for item in below_cost_items:
            below_cost_map.setdefault(str(item["invoice_id"]), []).append(item["medicine__name"])
        flagged_ids |= set(below_cost_map.keys())

        invoice_exceptions = []
        for inv in invoices_qs.filter(id__in=flagged_ids):
            overrides = []
            if inv.credit_override:
                overrides.append({
                    "type": "CREDIT_OVERRIDE",
                    "reason": inv.credit_override_reason,
                })
            if inv.fefo_override:
                overrides.append({
                    "type": "FEFO_OVERRIDE",
                    "reason": inv.fefo_override_reason,
                })
            if getattr(inv, "rx_override", False):
                overrides.append({
                    "type": "RX_OVERRIDE",
                    "reason": inv.rx_override_reason,
                })
            if inv.grand_total == 0:
                overrides.append({
                    "type": "ZERO_VALUE",
                    "reason": "Invoice grand total is zero",
                })
            if below_cost_map.get(str(inv.id)):
                overrides.append({
                    "type": "BELOW_COST",
                    "reason": f"Below cost: {', '.join(below_cost_map[str(inv.id)])}",
                })
            invoice_exceptions.append({
                "document_type": "SALES_INVOICE",
                "document_id": str(inv.id),
                "document_number": inv.number,
                "business_date": inv.business_date.isoformat(),
                "branch": str(inv.branch_id),
                "branch_name": inv.branch.name,
                "customer": str(inv.customer_id),
                "customer_name": inv.customer.name,
                "grand_total": str(money(inv.grand_total)),
                "confirmed_by": inv.confirmed_by.full_name if inv.confirmed_by else "",
                "confirmed_at": inv.confirmed_at.isoformat() if inv.confirmed_at else "",
                "overrides": overrides,
            })

        # Purchase duplicate overrides
        from apps.purchases.models import Purchase, PurchaseStatus
        purchase_qs = branch_scoped(
            request.user,
            Purchase.objects.filter(
                lifecycle=PurchaseStatus.CONFIRMED,
                business_date__range=(date_from, date_to),
                duplicate_invoice_override=True,
            ).select_related("supplier", "branch", "confirmed_by"),
        )

        purchase_exceptions = []
        for pur in purchase_qs:
            purchase_exceptions.append({
                "document_type": "PURCHASE",
                "document_id": str(pur.id),
                "document_number": pur.number,
                "business_date": pur.business_date.isoformat(),
                "branch": str(pur.branch_id),
                "branch_name": pur.branch.name,
                "supplier": str(pur.supplier_id),
                "supplier_name": pur.supplier.name,
                "grand_total": str(money(pur.grand_total)),
                "confirmed_by": pur.confirmed_by.full_name if pur.confirmed_by else "",
                "confirmed_at": pur.confirmed_at.isoformat() if pur.confirmed_at else "",
                "overrides": [{"type": "DUPLICATE_INVOICE", "reason": pur.duplicate_invoice_reason}],
            })

        all_exceptions = invoice_exceptions + purchase_exceptions
        all_exceptions.sort(key=lambda x: x["business_date"], reverse=True)

        filter_type = request.query_params.get("override_type", "")
        if filter_type:
            all_exceptions = [
                ex for ex in all_exceptions
                if any(o["type"] == filter_type for o in ex["overrides"])
            ]

        if request.query_params.get("export") == "csv":
            rows = []
            for ex in all_exceptions:
                for ov in ex["overrides"]:
                    rows.append([
                        ex["business_date"], ex["document_type"], ex["document_number"],
                        ex.get("customer_name", ex.get("supplier_name", "")),
                        ex["grand_total"], ov["type"], ov["reason"], ex["confirmed_by"],
                    ])
            return csv_response(
                "exceptions.csv",
                ["date", "type", "number", "party", "grand_total", "override_type", "reason", "confirmed_by"],
                rows,
            )

        return Response({
            "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            "total_exceptions": len(all_exceptions),
            "invoice_exceptions": len(invoice_exceptions),
            "purchase_exceptions": len(purchase_exceptions),
            "results": all_exceptions,
        })
