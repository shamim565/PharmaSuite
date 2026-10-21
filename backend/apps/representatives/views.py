from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.exceptions import ConflictError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin
from apps.representatives.models import Representative, SalesTarget, Territory
from apps.representatives.serializers import (
    RepresentativeAssignmentSerializer,
    RepresentativeSerializer,
    SalesTargetSerializer,
    TerritorySerializer,
)
from apps.representatives.services import assign, unassign


class TerritoryViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["REP_VIEW"],
        "retrieve": ["REP_VIEW"],
        "create": ["TERRITORY_MANAGE"],
        "update": ["TERRITORY_MANAGE"],
        "partial_update": ["TERRITORY_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = TerritorySerializer
    queryset = Territory.objects.select_related("parent")
    filterset_fields = ["territory_type", "is_active", "parent"]
    search_fields = ["name"]
    ordering = ["name"]


class RepresentativeViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["REP_VIEW"],
        "retrieve": ["REP_VIEW"],
        "create": ["REP_MANAGE"],
        "update": ["REP_MANAGE"],
        "partial_update": ["REP_MANAGE"],
        "me": [],
        "assignments": ["REP_VIEW"],
        "assign_target": ["REP_MANAGE"],
        "unassign_target": ["REP_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = RepresentativeSerializer
    queryset = Representative.objects.select_related("branch", "user", "reports_to")
    filterset_fields = ["rep_type", "branch", "is_active", "user"]
    search_fields = ["code", "name", "phone"]
    ordering = ["name"]

    def update(self, request, *args, **kwargs):
        representative = self.get_object()
        if request.data.get("is_active") is False:
            open_assignments = representative.assignments.filter(effective_to__isnull=True).count()
            if open_assignments:
                raise ConflictError(
                    "REP_HAS_ASSIGNMENTS",
                    f"Reassign or end {open_assignments} open assignment(s) before deactivating.",
                )
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """Return the representative profile linked to the signed-in user."""
        representative = (
            Representative.objects.select_related("branch", "user", "reports_to")
            .filter(user=request.user)
            .first()
        )
        if representative is None:
            return Response({"detail": "No representative profile linked."}, status=404)
        return Response(RepresentativeSerializer(representative).data)

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        rows = self.get_object().assignments.all()
        include_closed = request.query_params.get("include_closed") == "true"
        if not include_closed:
            rows = rows.filter(effective_to__isnull=True)
        return Response(RepresentativeAssignmentSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"], url_path="assign")
    def assign_target(self, request, pk=None):
        representative = self.get_object()
        entity_type = request.data.get("entity_type")
        entity_id = request.data.get("entity_id")
        if entity_type not in ("CUSTOMER", "DOCTOR", "TERRITORY") or not entity_id:
            raise ConflictError("INVALID_ASSIGNMENT", "entity_type and entity_id are required.")
        assignment = assign(representative=representative, entity_type=entity_type, entity_id=entity_id)
        return Response(RepresentativeAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="unassign")
    def unassign_target(self, request, pk=None):
        representative = self.get_object()
        entity_type = request.data.get("entity_type")
        entity_id = request.data.get("entity_id")
        if entity_type not in ("CUSTOMER", "DOCTOR", "TERRITORY") or not entity_id:
            raise ConflictError("INVALID_ASSIGNMENT", "entity_type and entity_id are required.")
        updated = unassign(representative=representative, entity_type=entity_type, entity_id=entity_id)
        return Response({"closed": updated})


class SalesTargetViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["REP_VIEW"],
        "retrieve": ["REP_VIEW"],
        "create": ["REP_MANAGE"],
        "update": ["REP_MANAGE"],
        "partial_update": ["REP_MANAGE"],
        "destroy": ["REP_MANAGE"],
    }
    permission_classes = [HasPermission]
    serializer_class = SalesTargetSerializer
    queryset = SalesTarget.objects.select_related("representative", "branch")
    filterset_fields = ["representative", "branch", "fiscal_year", "period_month"]
    ordering = ["-fiscal_year", "-period_month"]
