from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel, UUIDModel


class CustomerType(models.TextChoices):
    PHARMACY = "PHARMACY", "Pharmacy"
    RETAIL = "RETAIL", "Retail"
    HOSPITAL = "HOSPITAL", "Hospital"
    CLINIC = "CLINIC", "Clinic"


class PriceTier(models.TextChoices):
    RETAIL = "RETAIL", "Retail"
    WHOLESALE = "WHOLESALE", "Wholesale"
    CUSTOM = "CUSTOM", "Custom"


class Customer(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    customer_type = models.CharField(
        max_length=10, choices=CustomerType.choices, default=CustomerType.PHARMACY
    )
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    area = models.CharField(max_length=120, blank=True)
    price_tier = models.CharField(max_length=10, choices=PriceTier.choices, default=PriceTier.RETAIL)
    default_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    credit_days = models.PositiveIntegerField(default=0)
    credit_hold = models.BooleanField(default=False)
    credit_hold_reason = models.CharField(max_length=200, blank=True)
    balance_cache = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active"]), models.Index(fields=["area"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class CustomerLedgerEntryType(models.TextChoices):
    OPENING = "OPENING", "Opening"
    INVOICE = "INVOICE", "Invoice"
    PAYMENT = "PAYMENT", "Payment"
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL", "Payment reversal"
    SALES_RETURN = "SALES_RETURN", "Sales return"
    RETURN_REVERSAL = "RETURN_REVERSAL", "Return reversal"
    ADVANCE_APPLIED = "ADVANCE_APPLIED", "Advance applied"
    ADVANCE_REFUND = "ADVANCE_REFUND", "Advance refunded"
    WRITE_OFF = "WRITE_OFF", "Write-off"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


class CustomerLedgerEntry(UUIDModel):
    """Append-only receivable ledger. Receivable convention: invoice +, payment −."""

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="ledger_entries")
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="customer_ledger_entries"
    )
    entry_type = models.CharField(max_length=20, choices=CustomerLedgerEntryType.choices)
    amount_delta = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    source_number = models.CharField(max_length=40, blank=True)
    transaction_group_id = models.UUIDField(null=True, blank=True, db_index=True)
    reverses_entry = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    business_date = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["customer", "business_date"]),
            models.Index(fields=["source_type", "source_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount_delta=0), name="ck_customer_ledger_amount_nonzero"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount_delta} {self.customer_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Customer ledger entries are append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Customer ledger entries are append-only and cannot be deleted.")


class SalesInvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"


class SalesPaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Unpaid"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"


class SalesReturnStatus(models.TextChoices):
    NONE = "NONE", "None"
    PARTIALLY_RETURNED = "PARTIALLY_RETURNED", "Partially returned"
    FULLY_RETURNED = "FULLY_RETURNED", "Fully returned"


class FulfillmentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    DELIVERED = "DELIVERED", "Delivered"


class SalesInvoice(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="sales_invoices"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="sales_invoices"
    )
    doctor = models.ForeignKey(
        "doctors.Doctor", null=True, blank=True, on_delete=models.PROTECT, related_name="sales_invoices"
    )
    sales_rep = models.ForeignKey(
        "representatives.Representative",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
    )
    business_date = models.DateField(db_index=True)
    lifecycle = models.CharField(
        max_length=12, choices=SalesInvoiceStatus.choices, default=SalesInvoiceStatus.DRAFT
    )
    payment_status = models.CharField(
        max_length=16, choices=SalesPaymentStatus.choices, default=SalesPaymentStatus.UNPAID
    )
    return_status = models.CharField(
        max_length=20, choices=SalesReturnStatus.choices, default=SalesReturnStatus.NONE
    )
    fulfillment_status = models.CharField(
        max_length=10, choices=FulfillmentStatus.choices, default=FulfillmentStatus.PENDING
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    round_off = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    paid_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    returned_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)
    credit_override = models.BooleanField(default=False)
    credit_override_reason = models.TextField(blank=True)
    fefo_override = models.BooleanField(default=False)
    fefo_override_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["customer", "business_date"]),
            models.Index(fields=["customer", "due_date"]),
            models.Index(fields=["lifecycle"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0), name="ck_sales_invoice_grand_nonneg"
            ),
        ]

    def __str__(self) -> str:
        return self.number or f"sale draft {self.id}"

    @property
    def outstanding(self) -> Decimal:
        if self.lifecycle != SalesInvoiceStatus.CONFIRMED:
            return Decimal("0")
        return self.grand_total - self.paid_total

    @property
    def is_paid(self) -> bool:
        return self.payment_status == SalesPaymentStatus.PAID


class SalesInvoiceItem(BaseModel):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="items")
    line_no = models.PositiveIntegerField(default=1)
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="sales_invoice_items"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", null=True, blank=True, on_delete=models.PROTECT, related_name="sales_invoice_items"
    )
    batch_number = models.CharField(max_length=60, blank=True)
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    line_discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    line_net = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    is_free_goods = models.BooleanField(default=False)
    returned_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))

    class Meta:
        ordering = ["invoice", "line_no"]
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_sales_item_qty_positive"),
            models.UniqueConstraint(fields=["invoice", "line_no"], name="uq_sales_item_line"),
        ]

    @property
    def line_total(self) -> Decimal:
        return self.line_net + self.vat_amount

    @property
    def returnable_qty(self) -> Decimal:
        return self.qty - self.returned_qty


class SalesReturnReason(models.TextChoices):
    CUSTOMER_RETURN = "CUSTOMER_RETURN", "Customer return"
    DAMAGED = "DAMAGED", "Damaged"
    EXPIRED_AT_CUSTOMER = "EXPIRED_AT_CUSTOMER", "Expired at customer"
    WRONG_ITEM = "WRONG_ITEM", "Wrong item"
    EXCESS_SUPPLY = "EXCESS_SUPPLY", "Excess supply"


class ReturnCondition(models.TextChoices):
    RESELLABLE = "RESELLABLE", "Resellable"
    DAMAGED = "DAMAGED", "Damaged"
    EXPIRED = "EXPIRED", "Expired"


class RefundMethod(models.TextChoices):
    CUSTOMER_CREDIT = "CUSTOMER_CREDIT", "Customer credit"
    CASH = "CASH", "Cash refund"
    BANK = "BANK", "Bank refund"
    ADJUST_DUES = "ADJUST_DUES", "Adjust dues"


class SalesReturnDocStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    REVERSED = "REVERSED", "Reversed"


class SalesReturn(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    invoice = models.ForeignKey(
        SalesInvoice, on_delete=models.PROTECT, related_name="returns"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="sales_returns"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="sales_returns"
    )
    business_date = models.DateField(db_index=True)
    reason_code = models.CharField(max_length=25, choices=SalesReturnReason.choices)
    status = models.CharField(
        max_length=10, choices=SalesReturnDocStatus.choices, default=SalesReturnDocStatus.DRAFT
    )
    refund_method = models.CharField(
        max_length=20, choices=RefundMethod.choices, default=RefundMethod.CUSTOMER_CREDIT
    )
    refund_account = models.ForeignKey(
        "accounting.FinancialAccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sales_returns",
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_reversal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_reversal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
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
        indexes = [
            models.Index(fields=["customer", "business_date"]),
            models.Index(fields=["invoice"]),
        ]

    def __str__(self) -> str:
        return self.number or f"sales return draft {self.id}"


class SalesReturnItem(BaseModel):
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name="items")
    invoice_item = models.ForeignKey(
        SalesInvoiceItem, on_delete=models.PROTECT, related_name="return_items"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", on_delete=models.PROTECT, related_name="sales_return_items"
    )
    qty = models.DecimalField(max_digits=14, decimal_places=3)
    condition = models.CharField(max_length=10, choices=ReturnCondition.choices)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    discount_reversal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_reversal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    restocked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_sales_return_qty_positive"),
        ]

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.qty - self.discount_reversal + self.vat_reversal
