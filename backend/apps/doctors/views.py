from datetime import date

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Medicine, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.doctors.models import Doctor, DoctorMedicine, DoctorVisit
from apps.doctors.serializers import (
    DoctorMedicineSerializer,
    DoctorSerializer,
    DoctorVisitSerializer,
    VisitCompleteSerializer,
)
from apps.doctors.services import (
    complete_visit,
    end_medicine_mapping,
    mark_visit_missed,
    open_medicine_mapping,
    visit_coverage,
)


def scoped_branch(user, queryset, field: str = "branch_id"):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(**{f"{field}__in": user.branch_ids})


class DoctorViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["DOCTOR_VIEW"],
        "retrieve": ["DOCTOR_VIEW"],
        "create": ["DOCTOR_MANAGE"],
        "update": ["DOCTOR_MANAGE"],
        "partial_update": ["DOCTOR_MANAGE"],
        "medicines": ["DOCTOR_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.select_related("territory")
    filterset_fields = ["is_active", "specialty", "category", "doctor_type", "territory"]
    search_fields = ["code", "name", "phones", "specialty", "registration_no"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["get", "post"], url_path="medicines")
    def medicines(self, request, pk=None):
        doctor = self.get_object()
        if request.method == "GET":
            include_closed = request.query_params.get("include_closed") == "true"
            rows = doctor.medicine_mappings.select_related("medicine")
            if not include_closed:
                rows = rows.filter(effective_to__isnull=True)
            return Response(DoctorMedicineSerializer(rows, many=True).data)

        serializer = DoctorMedicineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = open_medicine_mapping(
            doctor=doctor,
            medicine=serializer.validated_data["medicine"],
            priority=serializer.validated_data.get("priority", ""),
            strength_note=serializer.validated_data.get("strength_note", ""),
        )
        return Response(DoctorMedicineSerializer(mapping).data, status=status.HTTP_201_CREATED)


class DoctorMedicineViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [HasPermission]
    required_permissions = ["DOCTOR_MANAGE"]
    serializer_class = DoctorMedicineSerializer
    queryset = DoctorMedicine.objects.select_related("medicine", "doctor")

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        mapping = end_medicine_mapping(mapping=self.get_object())
        return Response(DoctorMedicineSerializer(mapping).data)


class DoctorVisitViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["VISIT_VIEW"],
        "retrieve": ["VISIT_VIEW"],
        "create": ["VISIT_MANAGE"],
        "update": ["VISIT_MANAGE"],
        "partial_update": ["VISIT_MANAGE"],
        "complete": ["VISIT_MANAGE"],
        "miss": ["VISIT_MANAGE"],
    }
    permission_classes = [HasPermission]
    queryset = DoctorVisit.objects.select_related(
        "doctor", "representative", "branch"
    ).prefetch_related("samples__medicine", "samples__batch")
    filterset_fields = ["doctor", "representative", "branch", "status", "outcome"]
    search_fields = ["doctor__name", "representative__name", "notes", "purpose"]
    ordering_fields = ["planned_date", "visited_at", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = scoped_branch(self.request.user, super().get_queryset())
        planned_from = self.request.query_params.get("planned_from")
        planned_to = self.request.query_params.get("planned_to")
        if planned_from:
            qs = qs.filter(planned_date__gte=planned_from)
        if planned_to:
            qs = qs.filter(planned_date__lte=planned_to)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DoctorVisitSerializer
        return DoctorVisitSerializer

    def create(self, request, *args, **kwargs):
        serializer = DoctorVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = serializer.save(created_by=request.user)
        return Response(DoctorVisitSerializer(visit).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        visit = self.get_object()
        serializer = VisitCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        samples = []
        for sample in data.get("samples") or []:
            medicine = Medicine.objects.filter(id=sample["medicine"]).first()
            batch = MedicineBatch.objects.filter(id=sample["batch"]).first()
            if medicine is None or batch is None or str(batch.medicine_id) != str(medicine.id):
                raise APIError("INVALID_BATCH", "Sample batch/medicine not found or mismatched.")
            samples.append({"medicine": medicine, "batch": batch, "qty": sample["qty"]})

        visit = complete_visit(
            visit=visit,
            actor=request.user,
            visited_at=data.get("visited_at"),
            purpose=data.get("purpose", ""),
            products_discussed=data.get("products_discussed"),
            outcome=data.get("outcome", ""),
            next_visit_date=data.get("next_visit_date"),
            notes=data.get("notes", ""),
            samples=samples,
        )
        return Response(DoctorVisitSerializer(visit).data)

    @action(detail=True, methods=["post"])
    def miss(self, request, pk=None):
        visit = mark_visit_missed(
            visit=self.get_object(), reason=request.data.get("reason", ""), actor=request.user
        )
        return Response(DoctorVisitSerializer(visit).data)


class VisitCoverageView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["VISIT_VIEW"]

    def get(self, request):
        today = timezone.localdate()
        raw_from = request.query_params.get("date_from")
        raw_to = request.query_params.get("date_to")
        date_to = date.fromisoformat(raw_to) if raw_to else today
        date_from = date.fromisoformat(raw_from) if raw_from else date_to.replace(day=1)
        filters = {
            "branch": request.query_params.get("branch"),
            "representative": request.query_params.get("representative"),
        }
        data = visit_coverage(request.user, date_from, date_to, filters)
        return Response(
            {
                "period": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "count": len(data["results"]),
                "ad_hoc_completed": data["ad_hoc_completed"],
                "results": data["results"],
            }
        )
