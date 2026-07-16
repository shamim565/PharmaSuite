from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.suppliers.views import PayableSummaryView, SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")

urlpatterns = [
    path("", include(router.urls)),
    path("suppliers/reports/payables/", PayableSummaryView.as_view(), name="report-payables"),
]
