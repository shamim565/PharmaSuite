from django.db import models

from apps.common.models import BaseModel


class TerritoryType(models.TextChoices):
    REGION = "REGION", "Region"
    AREA = "AREA", "Area"
    TERRITORY = "TERRITORY", "Territory"


class RepresentativeType(models.TextChoices):
    SALES = "SALES", "Sales representative"
    MEDICAL = "MEDICAL", "Medical representative"


class AssignmentEntityType(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    DOCTOR = "DOCTOR", "Doctor"
    TERRITORY = "TERRITORY", "Territory"


class Territory(BaseModel):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    territory_type = models.CharField(
        max_length=12, choices=TerritoryType.choices, default=TerritoryType.TERRITORY
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "territories"
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uq_territory_parent_name")
        ]

    def __str__(self) -> str:
        return self.name


class Representative(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150, db_index=True)
    rep_type = models.CharField(
        max_length=10, choices=RepresentativeType.choices, default=RepresentativeType.SALES
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    branch = models.ForeignKey(
        "branches.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="representatives"
    )
    user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="representative_profile",
    )
    reports_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="direct_reports"
    )
    joined_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class RepresentativeAssignment(BaseModel):
    representative = models.ForeignKey(
        Representative, on_delete=models.CASCADE, related_name="assignments"
    )
    entity_type = models.CharField(max_length=12, choices=AssignmentEntityType.choices)
    entity_id = models.UUIDField(db_index=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["representative", "entity_type", "entity_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["representative", "entity_type", "entity_id"],
                condition=models.Q(effective_to__isnull=True),
                name="uq_open_assignment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.representative_id} -> {self.entity_type}:{self.entity_id}"
