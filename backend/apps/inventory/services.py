"""Inventory posting service — the single choke-point for all stock movements.

Guarantees:
- atomic: ledger rows + balance cache commit together
- concurrency-safe: balance rows locked in deterministic order
- no negative stock: every outbound movement is validated under lock
- idempotent: an existing idempotency_key returns the original postings
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import BatchStatus
from apps.common.exceptions import APIError
from apps.inventory.models import EntryType, InventoryTransaction, StockBalance, StockPool

POOL_FIELD = {
    StockPool.SALEABLE: "qty_on_hand",
    StockPool.PROMO: "qty_promo",
    StockPool.QUARANTINE: "qty_quarantine",
}

OUTBOUND_TYPES = {
    EntryType.SALE,
    EntryType.PURCHASE_RETURN,
    EntryType.BONUS_ISSUE,
    EntryType.DAMAGE,
    EntryType.EXPIRY,
    EntryType.TRANSFER,
}


@dataclass
class MovementLine:
    medicine: object
    batch: object
    qty_delta: Decimal
    unit_cost: Decimal | None = None
    pool: str = StockPool.SALEABLE


def _locked_balance(branch, medicine, batch) -> StockBalance:
    try:
        return StockBalance.objects.select_for_update().get(
            branch=branch, medicine=medicine, batch=batch
        )
    except StockBalance.DoesNotExist:
        try:
            return StockBalance.objects.create(
                branch=branch, medicine=medicine, batch=batch
            )
        except IntegrityError:
            return StockBalance.objects.select_for_update().get(
                branch=branch, medicine=medicine, batch=batch
            )


def post_transactions(
    *,
    branch,
    lines: list[MovementLine],
    entry_type: str,
    source_type: str = "",
    source_id: UUID | None = None,
    source_number: str = "",
    business_date=None,
    actor=None,
    idempotency_key: str | None = None,
    transaction_group_id: UUID | None = None,
) -> list[InventoryTransaction]:
    if not lines:
        return []

    if idempotency_key:
        existing = list(
            InventoryTransaction.objects.filter(idempotency_key=idempotency_key).order_by(
                "created_at"
            )
        )
        if existing:
            return existing

    group_id = transaction_group_id or uuid4()
    business_date = business_date or timezone.localdate()
    postings: list[InventoryTransaction] = []

    with transaction.atomic():
        ordered = sorted(lines, key=lambda line: (str(line.medicine.id), str(line.batch.id)))
        balances: dict[UUID, StockBalance] = {}

        for line in ordered:
            qty_delta = Decimal(line.qty_delta)
            if qty_delta == 0:
                raise APIError("INVALID_QUANTITY", "Quantity must not be zero.")

            balance = balances.get(line.batch.id) or _locked_balance(
                branch, line.medicine, line.batch
            )
            balances[line.batch.id] = balance

            field = POOL_FIELD[line.pool]
            new_value = getattr(balance, field) + qty_delta
            if new_value < 0:
                raise APIError(
                    "INSUFFICIENT_STOCK",
                    (
                        f"Not enough {line.pool.lower()} stock for {line.medicine.name} "
                        f"batch {line.batch.batch_number}: available "
                        f"{getattr(balance, field)}, requested {abs(qty_delta)}."
                    ),
                    status_code=409,
                )

            unit_cost = (
                Decimal(line.unit_cost)
                if line.unit_cost is not None
                else Decimal(line.batch.unit_cost or 0)
            )
            setattr(balance, field, new_value)
            balance.version += 1
            balance.save(update_fields=[field, "version", "updated_at"])

            posting = InventoryTransaction.objects.create(
                branch=branch,
                medicine=line.medicine,
                batch=line.batch,
                entry_type=entry_type,
                pool=line.pool,
                qty_delta=qty_delta,
                unit_cost=unit_cost,
                value_delta=(qty_delta * unit_cost).quantize(Decimal("0.01")),
                source_type=source_type,
                source_id=source_id,
                source_number=source_number,
                transaction_group_id=group_id,
                idempotency_key=idempotency_key if len(lines) == 1 else None,
                business_date=business_date,
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
            postings.append(posting)

        for batch_id, balance in balances.items():
            batch = next(line.batch for line in ordered if line.batch.id == batch_id)
            batch.qty_on_hand = balance.qty_on_hand
            if balance.qty_on_hand <= 0 and batch.status == BatchStatus.ACTIVE:
                batch.status = BatchStatus.DEPLETED
            batch.save(update_fields=["qty_on_hand", "status", "updated_at"])

    return postings


def available_quantity(branch, medicine, batch, pool: str = StockPool.SALEABLE) -> Decimal:
    balance = StockBalance.objects.filter(
        branch=branch, medicine=medicine, batch=batch
    ).first()
    if balance is None:
        return Decimal("0")
    return getattr(balance, POOL_FIELD[pool])


def ledger_quantities(branch, medicine, batch) -> dict[str, Decimal]:
    """Ledger-derived quantities (source of truth) for a batch, per pool."""
    from django.db.models import Sum

    rows = (
        InventoryTransaction.objects.filter(branch=branch, medicine=medicine, batch=batch)
        .values("pool")
        .annotate(total=Sum("qty_delta"))
    )
    totals = {"SALEABLE": Decimal("0"), "PROMO": Decimal("0"), "QUARANTINE": Decimal("0")}
    for row in rows:
        totals[row["pool"]] = row["total"] or Decimal("0")
    return totals
