from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import CustomerPaymentViewSet, DailyCollectionView

router = DefaultRouter()
router.register("payments", CustomerPaymentViewSet, basename="customer-payment")

urlpatterns = [
    path("", include(router.urls)),
    path("payments/reports/daily-collection/", DailyCollectionView.as_view(), name="report-daily-collection"),
]
