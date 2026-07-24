from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.doctors.views import (
    DoctorMedicineViewSet,
    DoctorViewSet,
    DoctorVisitViewSet,
    VisitCoverageView,
)

router = DefaultRouter()
router.register("doctors", DoctorViewSet, basename="doctor")
router.register("doctor-medicines", DoctorMedicineViewSet, basename="doctor-medicine")
router.register("doctor-visits", DoctorVisitViewSet, basename="doctor-visit")

urlpatterns = [
    path("", include(router.urls)),
    path("doctors/reports/visit-coverage/", VisitCoverageView.as_view(), name="report-visit-coverage"),
]
