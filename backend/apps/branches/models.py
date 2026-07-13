from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class BranchType(models.TextChoices):
    HEAD_OFFICE = "HEAD_OFFICE", "Head office"
    BRANCH = "BRANCH", "Branch"


class BranchStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Branch(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=BranchType.choices, default=BranchType.BRANCH)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    manager = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_branches",
    )
    bin = models.CharField(max_length=30, blank=True)
    vat_reg = models.CharField(max_length=30, blank=True)
    trade_license = models.CharField(max_length=60, blank=True)
    invoice_prefix = models.CharField(max_length=10, blank=True)
    opening_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=BranchStatus.choices, default=BranchStatus.ACTIVE)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.invoice_prefix:
            self.invoice_prefix = self.code[:10].upper()
        super().save(*args, **kwargs)
