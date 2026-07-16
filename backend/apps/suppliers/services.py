"""Supplier payable ledger helpers."""

from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.suppliers.models import Supplier, SupplierLedgerEntry


def post_ledger_entry(
    *,
    supplier: Supplier,
    branch,
    entry_type: str,
    amount_delta: Decimal,
    source_type: str = "",
    source_id: UUID | None = None,
    source_number: str = "",
    due_date=None,
    business_date=None,
    actor=None,
    idempotency_key: str | None = None,
    reverses_entry: SupplierLedgerEntry | None = None,
    transaction_group_id: UUID | None = None,
) -> SupplierLedgerEntry:
    amount_delta = Decimal(amount_delta)
    if amount_delta == 0:
        raise ValueError("Supplier ledger amount must not be zero.")

    if idempotency_key:
        existing = SupplierLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    entry = SupplierLedgerEntry.objects.create(
        supplier=supplier,
        branch=branch,
        entry_type=entry_type,
        amount_delta=amount_delta,
        due_date=due_date,
        source_type=source_type,
        source_id=source_id,
        source_number=source_number,
        transaction_group_id=transaction_group_id,
        reverses_entry=reverses_entry,
        idempotency_key=idempotency_key,
        business_date=business_date or timezone.localdate(),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    refresh_supplier_balance(supplier)
    return entry


def supplier_balance_from_ledger(supplier: Supplier) -> Decimal:
    total = SupplierLedgerEntry.objects.filter(supplier=supplier).aggregate(
        total=Sum("amount_delta")
    )["total"]
    return total or Decimal("0")


def refresh_supplier_balance(supplier: Supplier) -> Decimal:
    with transaction.atomic():
        locked = Supplier.objects.select_for_update().get(id=supplier.id)
        balance = supplier_balance_from_ledger(locked)
        locked.balance_cache = balance
        locked.save(update_fields=["balance_cache", "updated_at"])
    return balance
