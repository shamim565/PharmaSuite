from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import ChequeViewSet, CustomerPaymentViewSet, DailyCollectionView

router = DefaultRouter()
router.register("payments", CustomerPaymentViewSet, basename="customer-payment")
router.register("cheques", ChequeViewSet, basename="cheque")

urlpatterns = [
    path("", include(router.urls)),
    path("payments/reports/daily-collection/", DailyCollectionView.as_view(), name="report-daily-collection"),
]
