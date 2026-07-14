from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    GenericViewSet,
    ManufacturerViewSet,
    MedicineBatchViewSet,
    MedicineCategoryViewSet,
    MedicineUnitConversionViewSet,
    MedicineViewSet,
    UnitViewSet,
)

router = DefaultRouter()
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("medicines/conversions", MedicineUnitConversionViewSet, basename="medicine-conversion")
router.register("generics", GenericViewSet, basename="generic")
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")
router.register("medicine-categories", MedicineCategoryViewSet, basename="medicine-category")
router.register("units", UnitViewSet, basename="unit")
router.register("batches", MedicineBatchViewSet, basename="batch")

urlpatterns = [
    path("", include(router.urls)),
]
