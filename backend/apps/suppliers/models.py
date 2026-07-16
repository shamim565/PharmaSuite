from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel, UUIDModel


class SupplierType(models.TextChoices):
    MANUFACTURER = "MANUFACTURER", "Manufacturer"
    IMPORTER = "IMPORTER", "Importer"
    TRADER = "TRADER", "Trader"
    DISTRIBUTOR = "DISTRIBUTOR", "Distributor"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank transfer"
    MFS = "MFS", "Mobile financial service"
    CHEQUE = "CHEQUE", "Cheque"


class ExcessReturnHandling(models.TextChoices):
    ADVANCE = "ADVANCE", "Supplier advance"
    BLOCK = "BLOCK", "Block"


class SupplierLedgerEntryType(models.TextChoices):
    OPENING = "OPENING", "Opening"
    PURCHASE = "PURCHASE", "Purchase"
    PAYMENT = "PAYMENT", "Payment"
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL", "Payment reversal"
    PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase return"
    RETURN_REVERSAL = "RETURN_REVERSAL", "Return reversal"
    ADVANCE_APPLIED = "ADVANCE_APPLIED", "Advance applied"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


class Supplier(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    supplier_type = models.CharField(
        max_length=20, choices=SupplierType.choices, default=SupplierType.TRADER
    )
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    bin = models.CharField(max_length=30, blank=True)
    vat_reg = models.CharField(max_length=30, blank=True)
    trade_license = models.CharField(max_length=60, blank=True)
    credit_days = models.PositiveIntegerField(default=0)
    preferred_payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    bank_details = models.TextField(blank=True)
    excess_return_handling = models.CharField(
        max_length=10, choices=ExcessReturnHandling.choices, default=ExcessReturnHandling.ADVANCE
    )
    balance_cache = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class SupplierLedgerEntry(UUIDModel):
    """Append-only supplier (payable) ledger. Payable convention: purchase +, payment −."""

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="ledger_entries")
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="supplier_ledger_entries"
    )
    entry_type = models.CharField(max_length=20, choices=SupplierLedgerEntryType.choices)
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
            models.Index(fields=["supplier", "business_date"]),
            models.Index(fields=["source_type", "source_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount_delta=0), name="ck_supplier_ledger_amount_nonzero"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount_delta} {self.supplier_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Supplier ledger entries are append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Supplier ledger entries are append-only and cannot be deleted.")
