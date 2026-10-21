from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.representatives.views import RepresentativeViewSet, SalesTargetViewSet, TerritoryViewSet

router = DefaultRouter()
router.register("territories", TerritoryViewSet, basename="territory")
router.register("representatives", RepresentativeViewSet, basename="representative")
router.register("sales-targets", SalesTargetViewSet, basename="sales-target")


urlpatterns = [
    path("", include(router.urls)),
]
