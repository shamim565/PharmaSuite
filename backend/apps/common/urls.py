from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.common.api import (
    AttachmentDownloadView,
    AttachmentView,
    NotificationViewSet,
    PeriodViewSet,
    SearchView,
    SettingsView,
)

router = DefaultRouter()
router.register("periods", PeriodViewSet, basename="fiscal-period")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
    path("search/", SearchView.as_view(), name="search"),
    path("attachments/", AttachmentView.as_view(), name="attachments"),
    path("attachments/<uuid:attachment_id>/download/", AttachmentDownloadView.as_view(), name="attachment-download"),
    path("", include(router.urls)),
]
