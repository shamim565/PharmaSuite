from datetime import date

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_action
from apps.catalog.models import Medicine, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.schema import object_response
from apps.common.viewsets import PermissionMappedMixin
from apps.doctors.models import Doctor, DoctorMedicine, DoctorVisit, VisitStatus
from apps.doctors.serializers import (
    DoctorChamberSerializer,
    DoctorMedicineSerializer,
    DoctorSerializer,
    DoctorVisitSerializer,
    VisitCompleteSerializer,
)
from apps.doctors.services import (
    cancel_visit,
    complete_visit,
    end_medicine_mapping,
    mark_visit_missed,
    open_medicine_mapping,
    reverse_visit_samples,
    visit_coverage,
)


def scoped_branch(user, queryset, field: str = "branch_id"):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(**{f"{field}__in": user.branch_ids})


def _require_doctor_manage(user) -> None:
    if not (user.is_superuser or "DOCTOR_MANAGE" in user.effective_permission_codes):
        raise APIError(
            "PERMISSION_DENIED", "Permission DOCTOR_MANAGE is required.", status_code=403
        )


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
        "chambers": ["DOCTOR_VIEW"],
        "delete_chamber": ["DOCTOR_MANAGE"],
        "medicines": ["DOCTOR_VIEW"],
    }
    permission_classes = [HasPermission]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.select_related("territory")
    filterset_fields = ["is_active", "specialty", "category", "doctor_type", "territory"]
    search_fields = ["code", "name", "phones", "specialty", "registration_no"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]

    def perform_create(self, serializer):
        doctor = serializer.save()
        log_action(
            actor=self.request.user,
            action="DOCTOR_CREATED",
            entity_type="doctor",
            entity_id=doctor.id,
            after=DoctorSerializer(doctor).data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = DoctorSerializer(self.get_object()).data
        doctor = serializer.save()
        log_action(
            actor=self.request.user,
            action="DOCTOR_UPDATED",
            entity_type="doctor",
            entity_id=doctor.id,
            before=before,
            after=DoctorSerializer(doctor).data,
            request=self.request,
        )

    @action(detail=True, methods=["get", "post"], url_path="chambers")
    def chambers(self, request, pk=None):
        doctor = self.get_object()
        if request.method == "POST":
            _require_doctor_manage(request.user)
            serializer = DoctorChamberSerializer(data={**request.data, "doctor": doctor.id})
            serializer.is_valid(raise_exception=True)
            chamber = serializer.save()
            log_action(
                actor=request.user,
                action="DOCTOR_CHAMBER_ADDED",
                entity_type="doctor_chamber",
                entity_id=chamber.id,
                after=DoctorChamberSerializer(chamber).data,
                request=request,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        rows = doctor.chambers.all()
        return Response({"count": rows.count(), "results": DoctorChamberSerializer(rows, many=True).data})

    @action(detail=True, methods=["delete"], url_path="chambers/(?P<chamber_id>[^/.]+)")
    def delete_chamber(self, request, pk=None, chamber_id=None):
        from apps.doctors.models import DoctorChamber

        chamber = DoctorChamber.objects.filter(id=chamber_id, doctor_id=pk).first()
        if chamber is None:
            raise APIError("NOT_FOUND", "Chamber not found.")
        log_action(
            actor=request.user,
            action="DOCTOR_CHAMBER_DELETED",
            entity_type="doctor_chamber",
            entity_id=chamber.id,
            before=DoctorChamberSerializer(chamber).data,
            request=request,
        )
        chamber.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="medicines")
    def medicines(self, request, pk=None):
        doctor = self.get_object()
        if request.method == "GET":
            include_closed = request.query_params.get("include_closed") == "true"
            rows = doctor.medicine_mappings.select_related("medicine")
            if not include_closed:
                rows = rows.filter(effective_to__isnull=True)
            return Response(DoctorMedicineSerializer(rows, many=True).data)

        _require_doctor_manage(request.user)
        serializer = DoctorMedicineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = open_medicine_mapping(
            doctor=doctor,
            medicine=serializer.validated_data["medicine"],
            priority=serializer.validated_data.get("priority", ""),
            strength_note=serializer.validated_data.get("strength_note", ""),
        )
        log_action(
            actor=request.user,
            action="DOCTOR_MEDICINE_OPENED",
            entity_type="doctor_medicine",
            entity_id=mapping.id,
            after=DoctorMedicineSerializer(mapping).data,
            request=request,
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

    def update(self, request, *args, **kwargs):
        mapping = self.get_object()
        before = {"priority": mapping.priority, "strength_note": mapping.strength_note}
        response = super().update(request, *args, **kwargs)
        updated = self.get_object()
        log_action(
            actor=request.user,
            action="DOCTOR_MEDICINE_UPDATED",
            entity_type="doctor_medicine",
            entity_id=updated.id,
            before=before,
            after={"priority": updated.priority, "strength_note": updated.strength_note},
            request=request,
        )
        return response

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        mapping = end_medicine_mapping(mapping=self.get_object())
        log_action(
            actor=request.user,
            action="DOCTOR_MEDICINE_ENDED",
            entity_type="doctor_medicine",
            entity_id=mapping.id,
            after=DoctorMedicineSerializer(mapping).data,
            request=request,
        )
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
        "cancel": ["VISIT_MANAGE"],
        "reverse_samples": ["VISIT_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = DoctorVisitSerializer
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

    def _ensure_branch_in_scope(self, branch_id) -> None:
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return
        if str(branch_id) not in {str(branch) for branch in user.branch_ids}:
            raise APIError(
                "BRANCH_SCOPE_EXCEEDED",
                "You cannot manage visits for a branch outside your scope.",
                status_code=403,
            )

    def create(self, request, *args, **kwargs):
        serializer = DoctorVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._ensure_branch_in_scope(serializer.validated_data["branch"].id)
        visit = serializer.save(created_by=request.user)
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_CREATED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            after=DoctorVisitSerializer(visit).data,
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        visit = self.get_object()
        if visit.status != VisitStatus.PLANNED:
            raise APIError(
                "INVALID_STATUS_TRANSITION",
                "Only planned visits can be edited; use complete, miss or cancel.",
            )
        partial = kwargs.pop("partial", False)
        serializer = DoctorVisitSerializer(visit, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        branch = serializer.validated_data.get("branch") or visit.branch
        self._ensure_branch_in_scope(branch.id)
        before = DoctorVisitSerializer(visit).data
        serializer.save()
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_UPDATED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            before=before,
            after=DoctorVisitSerializer(visit).data,
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data)

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
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_COMPLETED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            after=DoctorVisitSerializer(visit).data,
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data)

    @action(detail=True, methods=["post"])
    def miss(self, request, pk=None):
        visit = mark_visit_missed(
            visit=self.get_object(), reason=request.data.get("reason", ""), actor=request.user
        )
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_MISSED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            after={"reason": visit.missed_reason},
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        visit = cancel_visit(
            visit=self.get_object(), reason=request.data.get("reason", ""), actor=request.user
        )
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_CANCELLED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            after={"reason": visit.cancel_reason},
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data)

    @action(detail=True, methods=["post"], url_path="reverse-samples")
    def reverse_samples(self, request, pk=None):
        visit = reverse_visit_samples(
            visit=self.get_object(),
            actor=request.user,
            reason=str(request.data.get("reason") or ""),
        )
        log_action(
            actor=request.user,
            action="DOCTOR_VISIT_SAMPLES_REVERSED",
            entity_type="doctor_visit",
            entity_id=visit.id,
            after={"reason": request.data.get("reason", "")},
            branch=visit.branch,
            request=request,
        )
        return Response(DoctorVisitSerializer(visit).data)


@object_response
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