
from django.db import models

from apps.common.models import BaseModel


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank transfer"
    MFS = "MFS", "Mobile financial service"
    CHEQUE = "CHEQUE", "Cheque"


class PaymentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVERSED = "REVERSED", "Reversed"


class Payment(BaseModel):
    """Customer receipt."""

    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="customer_payments"
    )
    customer = models.ForeignKey(
        "sales.Customer", on_delete=models.PROTECT, related_name="payments"
    )
    business_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    account = models.ForeignKey(
        "accounting.FinancialAccount", on_delete=models.PROTECT, related_name="customer_payments"
    )
    reference = models.CharField(max_length=80, blank=True)
    collector = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="collected_payments"
    )
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.ACTIVE)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    reversal_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_customer_payment_positive"),
        ]

    def __str__(self) -> str:
        return self.number or f"receipt {self.amount}"


class PaymentAllocation(BaseModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(
        "sales.SalesInvoice", on_delete=models.PROTECT, related_name="payment_allocations"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "invoice"], name="uq_customer_payment_allocation"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_customer_alloc_positive"),
        ]


class ChequeDirection(models.TextChoices):
    RECEIVED = "RECEIVED", "Received from customer"
    ISSUED = "ISSUED", "Issued to supplier"


class ChequeStatus(models.TextChoices):
    PENDING_DEPOSIT = "PENDING_DEPOSIT", "Pending deposit"
    DEPOSITED = "DEPOSITED", "Deposited"
    CLEARED = "CLEARED", "Cleared"
    BOUNCED = "BOUNCED", "Bounced"
    PENDING = "PENDING", "Pending payment"
    PAID = "PAID", "Paid"
    STOPPED = "STOPPED", "Stopped"


class Cheque(BaseModel):
    direction = models.CharField(max_length=10, choices=ChequeDirection.choices)
    status = models.CharField(max_length=20, choices=ChequeStatus.choices)
    number = models.CharField(max_length=40, db_index=True)
    bank_name = models.CharField(max_length=100)
    bank_branch = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date_issued = models.DateField()
    date_deposited = models.DateField(null=True, blank=True)
    date_cleared = models.DateField(null=True, blank=True)
    date_bounced = models.DateField(null=True, blank=True)
    date_paid = models.DateField(null=True, blank=True)
    date_stopped = models.DateField(null=True, blank=True)
    customer = models.ForeignKey(
        "sales.Customer", null=True, blank=True, on_delete=models.PROTECT,
        related_name="cheques_received",
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", null=True, blank=True, on_delete=models.PROTECT,
        related_name="cheques_issued",
    )
    invoice = models.ForeignKey(
        "sales.SalesInvoice", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cheques",
    )
    supplier_payment = models.ForeignKey(
        "purchases.SupplierPayment", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cheques",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="cheques_created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["supplier", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.direction} {self.number} {self.amount}"
