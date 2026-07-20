from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales.views import (
    CustomerAdvanceView,
    CustomerViewSet,
    DueListView,
    ReceivableAgingView,
    SalesInvoiceViewSet,
)

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("sales", SalesInvoiceViewSet, basename="sales-invoice")

urlpatterns = [
    path("sales/due-list/", DueListView.as_view(), name="sales-due-list"),
    path("sales/reports/receivable-aging/", ReceivableAgingView.as_view(), name="report-receivable-aging"),
    path("customers/reports/advances/", CustomerAdvanceView.as_view(), name="report-customer-advances"),
    path("", include(router.urls)),
]
