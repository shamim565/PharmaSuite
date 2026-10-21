from django.db import models

from apps.common.uuid7 import uuid7


class DocumentType(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase"
    PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase order"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT", "Supplier payment"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit note (purchase return)"
    SALES_INVOICE = "SALES_INVOICE", "Sales invoice"
    DELIVERY_CHALLAN = "DELIVERY_CHALLAN", "Delivery challan"
    RECEIPT = "RECEIPT", "Customer receipt"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note (sales return)"
    SUPPLIER_CREDIT_NOTE = "SUPPLIER_CREDIT_NOTE", "Supplier credit note"
    ADJUSTMENT = "ADJUSTMENT", "Stock adjustment"
    TRANSFER = "TRANSFER", "Stock transfer"
    EXPENSE = "EXPENSE", "Expense voucher"
    INCOME = "INCOME", "Income voucher"



class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class DocumentSequence(BaseModel):
    """Gapless, per-branch, per-fiscal-year document numbering."""

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="document_sequences"
    )
    doc_type = models.CharField(max_length=30, choices=DocumentType.choices)
    fiscal_year = models.PositiveSmallIntegerField()
    prefix = models.CharField(max_length=10)
    width = models.PositiveSmallIntegerField(default=6)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["branch", "doc_type", "fiscal_year"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "doc_type", "fiscal_year"], name="uq_sequence_scope"
            )
        ]

    def __str__(self) -> str:
        return f"{self.branch_id}/{self.doc_type}/{self.fiscal_year}"


class FiscalPeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    LOCKED = "LOCKED", "Locked"


class Setting(BaseModel):
    """Key/value company or branch settings. Company scope = branch null."""

    key = models.CharField(max_length=100)
    branch = models.ForeignKey(
        "branches.Branch", null=True, blank=True, on_delete=models.CASCADE, related_name="settings"
    )
    value = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "branch"], name="uq_setting_key_branch"),
            models.UniqueConstraint(
                fields=["key"], condition=models.Q(branch__isnull=True), name="uq_setting_company_key"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.key} ({self.branch_id or 'company'})"


class FiscalPeriod(BaseModel):
    """One fiscal month (July–June fiscal year) for posting locks."""

    fiscal_year = models.PositiveIntegerField()
    period_month = models.PositiveIntegerField()  # 1 = July, 12 = June
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=10, choices=FiscalPeriodStatus.choices, default=FiscalPeriodStatus.OPEN
    )
    locked_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_reason = models.TextField(blank=True)
    unlock_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    unlock_at = models.DateTimeField(null=True, blank=True)
    unlock_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["fiscal_year", "period_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_year", "period_month"], name="uq_fiscal_period_month"
            )
        ]

    def __str__(self) -> str:
        return f"FY{fiscal_year_for_display(self.fiscal_year)} P{self.period_month} {self.status}"


def fiscal_year_for_display(fiscal_year: int) -> str:
    return f"{fiscal_year}-{fiscal_year + 1}"


class NotificationCategory(models.TextChoices):
    STOCK = "STOCK", "Low stock alerts"
    EXPIRY = "EXPIRY", "Expiry alerts"
    DUES = "DUES", "Overdue dues alerts"
    APPROVALS = "APPROVALS", "Pending approval alerts"
    VISITS = "VISITS", "Visit reminders"


class NotificationPreference(BaseModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notification_preferences"
    )
    category = models.CharField(max_length=20, choices=NotificationCategory.choices)
    enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(
        default=False, help_text="Also send this category to the user's email address."
    )
    sms_enabled = models.BooleanField(
        default=False, help_text="Also send this category to the user's mobile as SMS."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"], name="uq_notification_preference"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.category}={self.enabled}"


class Notification(BaseModel):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=40, db_index=True)
    severity = models.CharField(
        max_length=10, choices=[("INFO", "Info"), ("WARNING", "Warning"), ("CRITICAL", "Critical")],
        default="INFO",
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    deep_link = models.CharField(max_length=200, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "created_at"])]

    def __str__(self) -> str:
        return f"{self.type} -> {self.user_id}"


class Attachment(BaseModel):
    owner_type = models.CharField(max_length=60, db_index=True)
    owner_id = models.UUIDField(db_index=True)
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    storage_key = models.CharField(max_length=400)
    checksum = models.CharField(max_length=64, blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner_type", "owner_id"])]

    def __str__(self) -> str:
        return f"{self.owner_type}:{self.owner_id} {self.file_name}"
