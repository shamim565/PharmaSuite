from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales.views import CustomerViewSet, ReceivableAgingView, SalesInvoiceViewSet

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("sales", SalesInvoiceViewSet, basename="sales-invoice")

urlpatterns = [
    path("", include(router.urls)),
    path("sales/reports/receivable-aging/", ReceivableAgingView.as_view(), name="report-receivable-aging"),
]
