from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import PermissionListView, RoleViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")

urlpatterns = [
    *router.urls,
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
]
