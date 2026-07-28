from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="")
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_type",
            "branch",
            "branch_name",
            "entity_type",
            "entity_id",
            "action",
            "before",
            "after",
            "request_id",
            "ip",
            "created_at",
        ]
