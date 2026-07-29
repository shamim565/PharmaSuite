import csv
import io

from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [HasPermission]
    required_permissions = ["AUDIT_VIEW"]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor", "branch")
    filterset_fields = ["entity_type", "entity_id", "action", "actor", "actor_type", "request_id", "branch"]
    search_fields = ["entity_type", "action", "request_id"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not (user.is_superuser or user.has_all_branch_scope):
            qs = qs.filter(branch_id__in=user.branch_ids)
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    @action(detail=False, methods=["get"])
    def export(self, request):
        user = request.user
        if not (user.is_superuser or "AUDIT_EXPORT" in user.effective_permission_codes):
            raise APIError(
                "PERMISSION_DENIED", "You do not have permission to export audit logs.", status_code=403
            )
        entries = self.filter_queryset(self.get_queryset())[:10000]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["created_at", "actor", "action", "entity_type", "entity_id", "request_id", "ip"]
        )
        for entry in entries:
            writer.writerow(
                [
                    entry.created_at.isoformat(),
                    entry.actor.full_name if entry.actor else "system",
                    entry.action,
                    entry.entity_type,
                    entry.entity_id or "",
                    entry.request_id,
                    entry.ip or "",
                ]
            )
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        return response
