from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel


class PurchaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"


class PurchasePaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Unpaid"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"


class PurchaseReturnStatus(models.TextChoices):
    NONE = "NONE", "None"
    PARTIALLY_RETURNED = "PARTIALLY_RETURNED", "Partially returned"
    FULLY_RETURNED = "FULLY_RETURNED", "Fully returned"


class SupplierPaymentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVERSED = "REVERSED", "Reversed"


class PurchaseReturnDocStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    REVERSED = "REVERSED", "Reversed"


class ReturnReason(models.TextChoices):
    DAMAGED = "DAMAGED", "Damaged"
    EXPIRED = "EXPIRED", "Expired"
    NEAR_EXPIRY_AGREEMENT = "NEAR_EXPIRY_AGREEMENT", "Near-expiry agreement"
    WRONG_ITEM = "WRONG_ITEM", "Wrong item"
    OVER_SUPPLY = "OVER_SUPPLY", "Over supply"


class Purchase(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="purchases"
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="purchases"
    )
    supplier_invoice_number = models.CharField(max_length=60)
    supplier_invoice_date = models.DateField()
    business_date = models.DateField(db_index=True)
    lifecycle = models.CharField(
        max_length=12, choices=PurchaseStatus.choices, default=PurchaseStatus.DRAFT
    )
    payment_status = models.CharField(
        max_length=16, choices=PurchasePaymentStatus.choices, default=PurchasePaymentStatus.UNPAID
    )
    return_status = models.CharField(
        max_length=20, choices=PurchaseReturnStatus.choices, default=PurchaseReturnStatus.NONE
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    freight_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    round_off = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    paid_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    returned_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)
    duplicate_invoice_override = models.BooleanField(default=False)
    duplicate_invoice_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        verbose_name_plural = "purchases"
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["supplier", "business_date"]),
            models.Index(fields=["lifecycle"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0), name="ck_purchase_grand_nonneg"
            ),
        ]

    def __str__(self) -> str:
        return self.number or f"draft {self.supplier_invoice_number}"

    @property
    def outstanding(self) -> Decimal:
        if self.lifecycle != PurchaseStatus.CONFIRMED:
            return Decimal("0")
        return self.grand_total - self.paid_total - Decimal("0")


class PurchaseItem(BaseModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    line_no = models.PositiveIntegerField(default=1)
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="purchase_items"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_items"
    )
    batch_number = models.CharField(max_length=60)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    entry_unit = models.ForeignKey(
        "catalog.Unit", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    conversion_factor = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("1"))
    qty_entered = models.DecimalField(max_digits=14, decimal_places=3)
    qty_base = models.DecimalField(max_digits=14, decimal_places=3)
    bonus_qty_entered = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    bonus_qty_base = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4)
    line_discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    line_net = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    base_unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    effective_unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    returned_qty_base = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))

    class Meta:
        ordering = ["purchase", "line_no"]
        constraints = [
            models.CheckConstraint(condition=models.Q(qty_base__gt=0), name="ck_purchase_item_qty_positive"),
            models.UniqueConstraint(fields=["purchase", "line_no"], name="uq_purchase_item_line"),
        ]

    @property
    def returnable_qty_base(self) -> Decimal:
        return (self.qty_base + self.bonus_qty_base) - self.returned_qty_base


class SupplierPayment(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="supplier_payments"
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="payments"
    )
    business_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=10, choices=[("CASH", "Cash"), ("BANK", "Bank"), ("MFS", "MFS"), ("CHEQUE", "Cheque")])
    account = models.ForeignKey(
        "accounting.FinancialAccount", on_delete=models.PROTECT, related_name="supplier_payments"
    )
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=10, choices=SupplierPaymentStatus.choices, default=SupplierPaymentStatus.ACTIVE
    )
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    reversal_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_supplier_payment_positive"),
        ]

    def __str__(self) -> str:
        return self.number or f"payment {self.amount}"


class SupplierPaymentAllocation(BaseModel):
    payment = models.ForeignKey(
        SupplierPayment, on_delete=models.CASCADE, related_name="allocations"
    )
    purchase = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name="payment_allocations"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "purchase"], name="uq_supplier_payment_allocation"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_supplier_alloc_positive"),
        ]


class PurchaseReturn(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    purchase = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name="returns"
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="purchase_returns"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="purchase_returns"
    )
    business_date = models.DateField(db_index=True)
    reason_code = models.CharField(max_length=30, choices=ReturnReason.choices)
    status = models.CharField(
        max_length=10, choices=PurchaseReturnDocStatus.choices, default=PurchaseReturnDocStatus.DRAFT
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    round_off = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]

    def __str__(self) -> str:
        return self.number or f"return draft {self.id}"


class PurchaseReturnItem(BaseModel):
    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name="items"
    )
    purchase_item = models.ForeignKey(
        PurchaseItem, on_delete=models.PROTECT, related_name="return_items"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", on_delete=models.PROTECT, related_name="purchase_return_items"
    )
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_purchase_return_qty_positive"),
        ]
