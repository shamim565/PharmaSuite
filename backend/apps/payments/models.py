
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
