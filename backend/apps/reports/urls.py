from django.urls import path

from apps.reports.views import (
    FinancialPositionView,
    InventoryValuationView,
    ProfitLossReportView,
    SalesByDoctorView,
    SalesByRepView,
)

urlpatterns = [
    path("profit-loss/", ProfitLossReportView.as_view(), name="report-profit-loss"),
    path("inventory-valuation/", InventoryValuationView.as_view(), name="report-inventory-valuation"),
    path("financial-position/", FinancialPositionView.as_view(), name="report-financial-position"),
    path("sales-by-doctor/", SalesByDoctorView.as_view(), name="report-sales-by-doctor"),
    path("sales-by-rep/", SalesByRepView.as_view(), name="report-sales-by-rep"),
]
