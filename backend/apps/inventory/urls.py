from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory.location_views import WarehouseLocationViewSet
from apps.inventory.views import (
    ExpiredReportView,
    InventoryTransactionViewSet,
    LedgerIntegrityView,
    LowStockReportView,
    NearExpiryReportView,
    StockAdjustmentViewSet,
    StockBalanceViewSet,
    StockSummaryView,
    StockTransferViewSet,
)

router = DefaultRouter()
router.register("transactions", InventoryTransactionViewSet, basename="inventory-transaction")
router.register("balances", StockBalanceViewSet, basename="stock-balance")
router.register("adjustments", StockAdjustmentViewSet, basename="stock-adjustment")
router.register("transfers", StockTransferViewSet, basename="stock-transfer")
router.register("locations", WarehouseLocationViewSet, basename="warehouse-location")

urlpatterns = [
    path("", include(router.urls)),
    path("summary/", StockSummaryView.as_view(), name="stock-summary"),
    path("reports/low-stock/", LowStockReportView.as_view(), name="report-low-stock"),
    path("reports/near-expiry/", NearExpiryReportView.as_view(), name="report-near-expiry"),
    path("reports/expired/", ExpiredReportView.as_view(), name="report-expired"),
    path("integrity/", LedgerIntegrityView.as_view(), name="inventory-integrity"),
]
