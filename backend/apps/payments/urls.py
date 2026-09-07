from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    ChequeViewSet,
    CustomerPaymentViewSet,
    DailyCollectionView,
    PaymentReceiptPdfView,
)

router = DefaultRouter()
router.register("payments", CustomerPaymentViewSet, basename="customer-payment")
router.register("cheques", ChequeViewSet, basename="cheque")

urlpatterns = [
    path("payments/<uuid:payment_id>/print/", PaymentReceiptPdfView.as_view(), name="customer-payment-pdf"),
    path("", include(router.urls)),
    path("payments/reports/daily-collection/", DailyCollectionView.as_view(), name="report-daily-collection"),
]
