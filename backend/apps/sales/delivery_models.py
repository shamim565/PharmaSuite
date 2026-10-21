
from django.db import models

from apps.common.models import BaseModel


class ChallanStatus(models.TextChoices):
    PREPARED = "PREPARED", "Prepared"
    DISPATCHED = "DISPATCHED", "Dispatched"
    DELIVERED = "DELIVERED", "Delivered"
    UNDELIVERED = "UNDELIVERED", "Undelivered"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryChallan(BaseModel):
    """Delivery Challan / Dispatch Note accompanying goods in transit to customer."""

    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="delivery_challans"
    )
    customer = models.ForeignKey(
        "sales.Customer", on_delete=models.PROTECT, related_name="delivery_challans"
    )
    invoice = models.ForeignKey(
        "sales.SalesInvoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_challans",
    )
    business_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=ChallanStatus.choices,
        default=ChallanStatus.PREPARED,
        db_index=True,
    )
    delivery_person = models.CharField(max_length=120, blank=True)
    delivery_phone = models.CharField(max_length=30, blank=True)
    vehicle_no = models.CharField(max_length=60, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatched_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    recipient_name = models.CharField(max_length=120, blank=True)
    recipient_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.number or f"Challan draft {self.id}"


class DeliveryChallanItem(BaseModel):
    challan = models.ForeignKey(DeliveryChallan, on_delete=models.CASCADE, related_name="items")
    line_no = models.PositiveIntegerField(default=1)
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="+"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    batch_number = models.CharField(max_length=60)
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["challan", "line_no"]
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_challan_item_qty_pos"),
            models.UniqueConstraint(fields=["challan", "line_no"], name="uq_challan_item_line"),
        ]

    def __str__(self) -> str:
        return f"{self.challan_id} Line {self.line_no}: {self.medicine_id} x {self.qty}"
