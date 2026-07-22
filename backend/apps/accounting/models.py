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
    REFUND = "REFUND", "Customer refund"
    EXPENSE = "EXPENSE", "Expense"
    EXPENSE_REVERSAL = "EXPENSE_REVERSAL", "Expense reversal"
    INCOME = "INCOME", "Other income"
    INCOME_REVERSAL = "INCOME_REVERSAL", "Income reversal"


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


class ExpenseStatus(models.TextChoices):
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
    POSTED = "POSTED", "Posted"
    REJECTED = "REJECTED", "Rejected"
    REVERSED = "REVERSED", "Reversed"


class IncomeStatus(models.TextChoices):
    POSTED = "POSTED", "Posted"
    REVERSED = "REVERSED", "Reversed"


class ExpenseCategory(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense categories"

    def __str__(self) -> str:
        return self.name


class IncomeCategory(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "income categories"

    def __str__(self) -> str:
        return self.name


class Expense(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="expenses"
    )
    business_date = models.DateField(db_index=True)
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(
        FinancialAccount, on_delete=models.PROTECT, related_name="expenses"
    )
    payee = models.CharField(max_length=150, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=ExpenseStatus.choices, default=ExpenseStatus.PENDING_APPROVAL
    )
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses"
    )
    approved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_expense_amount_positive"),
        ]

    def __str__(self) -> str:
        return self.number or f"expense {self.amount}"


class Income(BaseModel):
    number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="incomes"
    )
    business_date = models.DateField(db_index=True)
    category = models.ForeignKey(
        IncomeCategory, on_delete=models.PROTECT, related_name="incomes"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey(
        FinancialAccount, on_delete=models.PROTECT, related_name="incomes"
    )
    source = models.CharField(max_length=150, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=IncomeStatus.choices, default=IncomeStatus.POSTED
    )
    posted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="incomes"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "business_date"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_income_amount_positive"),
        ]

    def __str__(self) -> str:
        return self.number or f"income {self.amount}"
