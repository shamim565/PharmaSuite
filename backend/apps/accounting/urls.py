from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounting.views import FinancialAccountViewSet

router = DefaultRouter()
router.register("accounts", FinancialAccountViewSet, basename="financial-account")

urlpatterns = [
    path("", include(router.urls)),
]
