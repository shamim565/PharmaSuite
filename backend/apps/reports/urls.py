from django.urls import path

from apps.reports.views import (
    FinancialPositionView,
    InventoryValuationView,
    ProfitLossReportView,
)

urlpatterns = [
    path("profit-loss/", ProfitLossReportView.as_view(), name="report-profit-loss"),
    path("inventory-valuation/", InventoryValuationView.as_view(), name="report-inventory-valuation"),
    path("financial-position/", FinancialPositionView.as_view(), name="report-financial-position"),
]
