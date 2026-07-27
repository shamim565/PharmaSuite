from django.urls import path

from apps.reports.views import (
    FinancialPositionView,
    InventoryValuationView,
    ProfitLossReportView,
    PurchasesSummaryView,
    SalesByCustomerView,
    SalesByDoctorView,
    SalesByItemView,
    SalesByRepView,
    SalesSummaryView,
)

urlpatterns = [
    path("profit-loss/", ProfitLossReportView.as_view(), name="report-profit-loss"),
    path("inventory-valuation/", InventoryValuationView.as_view(), name="report-inventory-valuation"),
    path("financial-position/", FinancialPositionView.as_view(), name="report-financial-position"),
    path("sales-by-doctor/", SalesByDoctorView.as_view(), name="report-sales-by-doctor"),
    path("sales-by-rep/", SalesByRepView.as_view(), name="report-sales-by-rep"),
    path("sales-summary/", SalesSummaryView.as_view(), name="report-sales-summary"),
    path("purchases-summary/", PurchasesSummaryView.as_view(), name="report-purchases-summary"),
    path("sales-by-item/", SalesByItemView.as_view(), name="report-sales-by-item"),
    path("sales-by-customer/", SalesByCustomerView.as_view(), name="report-sales-by-customer"),
]
