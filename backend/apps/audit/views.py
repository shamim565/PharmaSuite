from rest_framework import mixins, viewsets

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
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
