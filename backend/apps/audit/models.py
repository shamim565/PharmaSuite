from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.common.models import BaseModel


class ActorType(models.TextChoices):
    USER = "USER", "User"
    SYSTEM = "SYSTEM", "System"


class AuditLog(BaseModel):
    """Append-only audit trail. Never updated or deleted from the application."""

    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    actor_type = models.CharField(max_length=10, choices=ActorType.choices, default=ActorType.USER)
    branch = models.ForeignKey(
        "branches.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    entity_type = models.CharField(max_length=80, db_index=True)
    entity_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=50, db_index=True)
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    request_id = models.CharField(max_length=64, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = []
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id}"
