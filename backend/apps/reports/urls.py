from django.urls import path

from apps.reports.bi_views import (
    CollectionEfficiencyView,
    ExceptionReportView,
    InventoryDSIView,
    MarginAnalysisView,
    RepPerformanceView,
    SupplierConcentrationView,
)
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
    # BI Reports
    path("inventory-dsi/", InventoryDSIView.as_view(), name="report-inventory-dsi"),
    path("margin-analysis/", MarginAnalysisView.as_view(), name="report-margin-analysis"),
    path("rep-performance/", RepPerformanceView.as_view(), name="report-rep-performance"),
    path("collection-efficiency/", CollectionEfficiencyView.as_view(), name="report-collection-efficiency"),
    path("supplier-concentration/", SupplierConcentrationView.as_view(), name="report-supplier-concentration"),
    path("exceptions/", ExceptionReportView.as_view(), name="report-exceptions"),
]
