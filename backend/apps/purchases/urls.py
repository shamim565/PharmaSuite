from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchases.views import (
    PayableAgingView,
    PurchaseReturnViewSet,
    PurchaseViewSet,
    SupplierPaymentViewSet,
)

router = DefaultRouter()
router.register("purchases", PurchaseViewSet, basename="purchase")
router.register("supplier-payments", SupplierPaymentViewSet, basename="supplier-payment")
router.register("purchase-returns", PurchaseReturnViewSet, basename="purchase-return")

urlpatterns = [
    path("", include(router.urls)),
    path("purchases/reports/payable-aging/", PayableAgingView.as_view(), name="report-payable-aging"),
]
