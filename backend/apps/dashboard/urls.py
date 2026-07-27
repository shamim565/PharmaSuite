from django.urls import path

from apps.dashboard.views import DashboardSummaryView, DashboardWidgetsView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("widgets/", DashboardWidgetsView.as_view(), name="dashboard-widgets"),
]
