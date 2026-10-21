from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchases.credit_views import SupplierCreditNoteViewSet
from apps.purchases.po_views import PurchaseOrderViewSet
from apps.purchases.views import (
    PayableAgingView,
    PurchasePdfView,
    PurchaseReturnViewSet,
    PurchaseViewSet,
    SupplierPaymentViewSet,
)

router = DefaultRouter()
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-order")
router.register("purchases", PurchaseViewSet, basename="purchase")
router.register("supplier-payments", SupplierPaymentViewSet, basename="supplier-payment")
router.register("purchase-returns", PurchaseReturnViewSet, basename="purchase-return")
router.register("supplier-credit-notes", SupplierCreditNoteViewSet, basename="supplier-credit-note")


urlpatterns = [
    path("purchases/<uuid:purchase_id>/print/", PurchasePdfView.as_view(), name="purchase-pdf"),
    path("", include(router.urls)),
    path("purchases/reports/payable-aging/", PayableAgingView.as_view(), name="report-payable-aging"),
]
