from django.http import JsonResponse
from django.urls import include, path

from apps.common.views import DeepHealthView


def health(request):
    return JsonResponse({"status": "ok", "service": "medicine-dealer-erp-api"})


urlpatterns = [
    path("api/v1/health/", health, name="health"),
    path("api/v1/health/deep/", DeepHealthView.as_view(), name="health-deep"),
    path("api/v1/auth/", include("apps.accounts.urls_auth")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.branches.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.suppliers.urls")),
    path("api/v1/", include("apps.purchases.urls")),
    path("api/v1/", include("apps.accounting.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
]
