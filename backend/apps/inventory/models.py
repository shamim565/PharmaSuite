from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel, UUIDModel


class EntryType(models.TextChoices):
    OPENING = "OPENING", "Opening"
    PURCHASE = "PURCHASE", "Purchase"
    BONUS = "BONUS", "Purchase bonus"
    SALE = "SALE", "Sale"
    SALES_RETURN = "SALES_RETURN", "Sales return"
    PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase return"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    BONUS_ISSUE = "BONUS_ISSUE", "Bonus / sample issue"
    DAMAGE = "DAMAGE", "Damage"
    EXPIRY = "EXPIRY", "Expiry write-off"
    TRANSFER = "TRANSFER", "Transfer"
    REVERSAL = "REVERSAL", "Reversal"


class StockPool(models.TextChoices):
    SALEABLE = "SALEABLE", "Saleable"
    PROMO = "PROMO", "Promotional"
    QUARANTINE = "QUARANTINE", "Quarantine"


class InventoryTransaction(UUIDModel):
    """Append-only stock ledger. Rows are never updated or deleted."""

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    entry_type = models.CharField(max_length=20, choices=EntryType.choices, db_index=True)
    pool = models.CharField(max_length=12, choices=StockPool.choices, default=StockPool.SALEABLE)
    qty_delta = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    value_delta = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    source_number = models.CharField(max_length=40, blank=True)
    transaction_group_id = models.UUIDField(db_index=True)
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
            models.Index(fields=["branch", "medicine", "batch", "created_at"]),
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["entry_type", "business_date"]),
        ]
        constraints = [
            models.CheckConstraint(condition=~models.Q(qty_delta=0), name="ck_inv_txn_qty_nonzero"),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.qty_delta} {self.medicine_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Inventory transactions are append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Inventory transactions are append-only and cannot be deleted.")


class StockBalance(BaseModel):
    """Derived cache of the stock ledger — authoritative source is InventoryTransaction."""

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="stock_balances"
    )
    medicine = models.ForeignKey(
        "catalog.Medicine", on_delete=models.PROTECT, related_name="stock_balances"
    )
    batch = models.ForeignKey(
        "catalog.MedicineBatch", on_delete=models.PROTECT, related_name="stock_balances"
    )
    qty_on_hand = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    qty_promo = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    qty_quarantine = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    version = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "stock balances"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "medicine", "batch"], name="uq_stock_balance_key"
            ),
            models.CheckConstraint(
                condition=models.Q(qty_on_hand__gte=0), name="ck_balance_on_hand_nonneg"
            ),
            models.CheckConstraint(
                condition=models.Q(qty_promo__gte=0), name="ck_balance_promo_nonneg"
            ),
            models.CheckConstraint(
                condition=models.Q(qty_quarantine__gte=0), name="ck_balance_quarantine_nonneg"
            ),
        ]
        indexes = [models.Index(fields=["branch", "medicine"])]

    def __str__(self) -> str:
        return f"{self.batch_id}: {self.qty_on_hand} on hand"
