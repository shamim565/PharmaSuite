from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.common.api import PeriodViewSet, SettingsView

router = DefaultRouter()
router.register("periods", PeriodViewSet, basename="fiscal-period")

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
    path("", include(router.urls)),
]
