from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel, UUIDModel


class AccountType(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    MFS = "MFS", "Mobile financial service"


class FinancialEntryType(models.TextChoices):
    OPENING = "OPENING", "Opening"
    PURCHASE_PAYMENT = "PURCHASE_PAYMENT", "Purchase payment"
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL", "Payment reversal"
    SALE_RECEIPT = "SALE_RECEIPT", "Sale receipt"
    RECEIPT_REVERSAL = "RECEIPT_REVERSAL", "Receipt reversal"
    DEPOSIT = "DEPOSIT", "Deposit"
    WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
    TRANSFER_IN = "TRANSFER_IN", "Transfer in"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"


class FinancialAccount(BaseModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=10, choices=AccountType.choices, default=AccountType.CASH)
    branch = models.ForeignKey(
        "branches.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="financial_accounts"
    )
    provider = models.CharField(max_length=80, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    allow_negative = models.BooleanField(default=False)
    balance_cache = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class FinancialTransaction(UUIDModel):
    """Append-only account ledger."""

    account = models.ForeignKey(
        FinancialAccount, on_delete=models.PROTECT, related_name="transactions"
    )
    entry_type = models.CharField(max_length=20, choices=FinancialEntryType.choices)
    amount_delta = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=80, blank=True)
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
        indexes = [models.Index(fields=["account", "business_date"])]
        constraints = [
            models.CheckConstraint(condition=~models.Q(amount_delta=0), name="ck_fin_txn_amount_nonzero"),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount_delta} {self.account_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Financial transactions are append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Financial transactions are append-only and cannot be deleted.")
