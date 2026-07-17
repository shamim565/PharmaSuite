from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import CustomerPaymentViewSet

router = DefaultRouter()
router.register("payments", CustomerPaymentViewSet, basename="customer-payment")

urlpatterns = [
    path("", include(router.urls)),
]
