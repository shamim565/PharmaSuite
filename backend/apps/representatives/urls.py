from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.representatives.views import RepresentativeViewSet, TerritoryViewSet

router = DefaultRouter()
router.register("territories", TerritoryViewSet, basename="territory")
router.register("representatives", RepresentativeViewSet, basename="representative")

urlpatterns = [
    path("", include(router.urls)),
]
