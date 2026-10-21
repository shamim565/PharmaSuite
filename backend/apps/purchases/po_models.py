from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
    FULLY_RECEIVED = "FULLY_RECEIVED", "Fully received"
    CANCELLED = "CANCELLED", "Cancelled"


class PurchaseOrder(BaseModel):
    """Purchase Order raised to a supplier before goods arrive."""

    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    business_date = models.DateField(db_index=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=PurchaseOrderStatus.choices, default=PurchaseOrderStatus.DRAFT, db_index=True
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Link to the confirmed purchase (GRN) that fully fulfills this PO
    fulfilled_by = models.ForeignKey(
        "purchases.Purchase", null=True, blank=True, on_delete=models.SET_NULL, related_name="fulfills_po"
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["supplier", "status"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0), name="ck_po_grand_nonneg"
            ),
        ]

    def __str__(self) -> str:
        return self.number or f"PO draft {self.id}"


class PurchaseOrderItem(BaseModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    line_no = models.PositiveIntegerField(default=1)
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="po_items"
    )
    qty_ordered = models.DecimalField(max_digits=14, decimal_places=3)
    qty_received = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    line_discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    line_net = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["purchase_order", "line_no"]
        constraints = [
            models.CheckConstraint(condition=models.Q(qty_ordered__gt=0), name="ck_po_item_qty_positive"),
            models.UniqueConstraint(fields=["purchase_order", "line_no"], name="uq_po_item_line"),
        ]

    @property
    def qty_pending(self) -> Decimal:
        return self.qty_ordered - self.qty_received

    @property
    def is_fully_received(self) -> bool:
        return self.qty_received >= self.qty_ordered
