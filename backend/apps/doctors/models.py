from django.db import models

from apps.common.models import BaseModel


class DoctorType(models.TextChoices):
    CONSULTANT = "CONSULTANT", "Consultant"
    GP = "GP", "General practitioner"
    OTHER = "OTHER", "Other"


class DoctorCategory(models.TextChoices):
    A = "A", "A"
    B = "B", "B"
    C = "C", "C"


class VisitStatus(models.TextChoices):
    PLANNED = "PLANNED", "Planned"
    COMPLETED = "COMPLETED", "Completed"
    MISSED = "MISSED", "Missed"
    CANCELLED = "CANCELLED", "Cancelled"


class VisitOutcome(models.TextChoices):
    INTERESTED = "INTERESTED", "Interested"
    NEUTRAL = "NEUTRAL", "Neutral"
    NOT_INTERESTED = "NOT_INTERESTED", "Not interested"
    PRESCRIBING = "PRESCRIBING", "Prescribing"


class Doctor(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150, db_index=True)
    gender = models.CharField(max_length=10, blank=True)
    phones = models.JSONField(default=list, blank=True)
    email = models.EmailField(blank=True)
    specialty = models.CharField(max_length=120, blank=True, db_index=True)
    degrees = models.CharField(max_length=200, blank=True)
    doctor_type = models.CharField(
        max_length=12, choices=DoctorType.choices, default=DoctorType.CONSULTANT
    )
    registration_no = models.CharField(max_length=50, null=True, blank=True, unique=True)
    category = models.CharField(max_length=2, choices=DoctorCategory.choices, default=DoctorCategory.B)
    potential_rating = models.CharField(max_length=10, blank=True)
    territory = models.ForeignKey(
        "representatives.Territory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="doctors",
    )
    visit_frequency_target = models.PositiveIntegerField(null=True, blank=True)
    consent_note = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active"]), models.Index(fields=["specialty"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class DoctorChamber(BaseModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="chambers")
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=250, blank=True)
    visiting_hours = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["doctor", "name"]


class DoctorMedicine(BaseModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="medicine_mappings")
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="doctor_mappings"
    )
    priority = models.CharField(max_length=10, blank=True)
    strength_note = models.CharField(max_length=200, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["doctor", "medicine"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "medicine"],
                condition=models.Q(effective_to__isnull=True),
                name="uq_open_doctor_medicine",
            )
        ]

    def __str__(self) -> str:
        return f"{self.doctor_id} -> {self.medicine_id}"


class DoctorVisit(BaseModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="visits")
    representative = models.ForeignKey(
        "representatives.Representative", on_delete=models.PROTECT, related_name="visits"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="doctor_visits"
    )
    status = models.CharField(max_length=10, choices=VisitStatus.choices, default=VisitStatus.PLANNED)
    planned_date = models.DateField(null=True, blank=True)
    visited_at = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=200, blank=True)
    products_discussed = models.JSONField(default=list, blank=True)
    outcome = models.CharField(max_length=15, choices=VisitOutcome.choices, blank=True)
    next_visit_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    missed_reason = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-visited_at", "-planned_date", "-created_at"]
        indexes = [
            models.Index(fields=["representative", "status"]),
            models.Index(fields=["doctor", "status"]),
            models.Index(fields=["branch", "planned_date"]),
        ]

    def __str__(self) -> str:
        return f"visit {self.doctor_id} by {self.representative_id}"


class DoctorVisitSample(BaseModel):
    visit = models.ForeignKey(DoctorVisit, on_delete=models.CASCADE, related_name="samples")
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="visit_samples"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", on_delete=models.PROTECT, related_name="visit_samples"
    )
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    inventory_transaction = models.ForeignKey(
        "inventory.InventoryTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="visit_samples",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_visit_sample_qty_positive")
        ]
