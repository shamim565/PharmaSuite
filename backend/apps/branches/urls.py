from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.branches.views import BranchViewSet

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [
    path("", include(router.urls)),
]
