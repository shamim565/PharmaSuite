from django.db import models

from apps.common.uuid7 import uuid7


class DocumentType(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT", "Supplier payment"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit note (purchase return)"
    SALES_INVOICE = "SALES_INVOICE", "Sales invoice"
    RECEIPT = "RECEIPT", "Customer receipt"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note (sales return)"
    ADJUSTMENT = "ADJUSTMENT", "Stock adjustment"


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
