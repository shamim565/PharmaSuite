
from django.db import models

from apps.common.models import BaseModel


class SupplierCreditNoteStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    SETTLED = "SETTLED", "Settled"
    CANCELLED = "CANCELLED", "Cancelled"


class SupplierCreditNoteReason(models.TextChoices):
    EXPIRY_RETURN = "EXPIRY_RETURN", "Expired goods return"
    DAMAGED_RETURN = "DAMAGED_RETURN", "Damaged goods return"
    PRICE_ADJUSTMENT = "PRICE_ADJUSTMENT", "Price adjustment"
    OTHER = "OTHER", "Other"


class SupplierCreditNote(BaseModel):
    """Credit note issued by a supplier (e.g. for returned expired goods).

    Settling a credit note posts a negative entry to the supplier ledger,
    reducing the payable — mirroring the purchase-return ledger semantics.
    """

    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="supplier_credit_notes"
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="credit_notes"
    )
    business_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason_code = models.CharField(
        max_length=30, choices=SupplierCreditNoteReason.choices, default=SupplierCreditNoteReason.OTHER
    )
    reference = models.CharField(max_length=120, blank=True, help_text="Supplier's credit note number")
    status = models.CharField(
        max_length=20, choices=SupplierCreditNoteStatus.choices,
        default=SupplierCreditNoteStatus.OPEN, db_index=True,
    )
    notes = models.TextField(blank=True)
    adjustment = models.ForeignKey(
        "inventory.StockAdjustment",
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="supplier_credit_notes",
        help_text="Optional link to the expiry write-off that generated this credit.",
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    settled_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["supplier", "status"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_scn_amount_positive"),
        ]

    @property
    def days_open(self) -> int | None:
        from django.utils import timezone

        if self.status != SupplierCreditNoteStatus.OPEN:
            return None
        return (timezone.localdate() - self.business_date).days

    def __str__(self) -> str:
        return self.number or f"Credit note draft {self.id}"
