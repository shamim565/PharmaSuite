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

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import BatchStatus, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.inventory.models import (
    AdjustmentStatus,
    EntryType,
    InventoryTransaction,
    StockAdjustment,
    StockAdjustmentItem,
    StockBalance,
    StockPool,
)

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

    from apps.common.periods import ensure_period_open

    ensure_period_open(business_date, actor)

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
            elif balance.qty_on_hand > 0 and batch.status == BatchStatus.DEPLETED:
                batch.status = BatchStatus.ACTIVE
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


# --------------------------------------------------------------------------- stock adjustments

REASON_ENTRY_TYPE = {
    "DAMAGE": EntryType.DAMAGE,
    "EXPIRY_WRITE_OFF": EntryType.EXPIRY,
    "RECALL_DISPOSAL": EntryType.EXPIRY,
}


def _movement_lines_for(adjustment: StockAdjustment) -> list[MovementLine]:
    lines: list[MovementLine] = []
    sign = Decimal("1") if adjustment.adjustment_type == "INCREASE" else Decimal("-1")
    for item in adjustment.items.select_related("medicine", "batch"):
        lines.append(
            MovementLine(
                medicine=item.medicine,
                batch=item.batch,
                qty_delta=sign * item.qty,
                unit_cost=item.unit_cost,
                pool=item.pool,
            )
        )
        if adjustment.adjustment_type == "DECREASE" and item.target_pool:
            lines.append(
                MovementLine(
                    medicine=item.medicine,
                    batch=item.batch,
                    qty_delta=item.qty,
                    unit_cost=item.unit_cost,
                    pool=item.target_pool,
                )
            )
    return lines


def _post_stock_adjustment(adjustment: StockAdjustment, actor) -> None:
    post_transactions(
        branch=adjustment.branch,
        lines=_movement_lines_for(adjustment),
        entry_type=REASON_ENTRY_TYPE.get(adjustment.reason_code, EntryType.ADJUSTMENT),
        source_type="STOCK_ADJUSTMENT",
        source_id=adjustment.id,
        source_number=adjustment.number or "",
        business_date=adjustment.business_date,
        actor=actor,
    )
    adjustment.number = adjustment.number or allocate_number(
        branch=adjustment.branch,
        doc_type=DocumentType.ADJUSTMENT,
        business_date=adjustment.business_date,
    )
    adjustment.status = AdjustmentStatus.POSTED
    adjustment.posted_at = timezone.now()
    adjustment.save(update_fields=["number", "status", "posted_at", "updated_at"])


@transaction.atomic
def create_stock_adjustment(
    *,
    branch,
    adjustment_type: str,
    reason_code: str,
    business_date=None,
    notes: str = "",
    items_data: list[dict],
    actor=None,
    idempotency_key: str | None = None,
) -> StockAdjustment:
    if not items_data:
        raise APIError("EMPTY_ADJUSTMENT", "A stock adjustment must have at least one line.")
    if idempotency_key:
        existing = StockAdjustment.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    adjustment = StockAdjustment.objects.create(
        branch=branch,
        business_date=business_date or timezone.localdate(),
        adjustment_type=adjustment_type,
        reason_code=reason_code,
        notes=notes,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
    )

    total_value = Decimal("0")
    for row in items_data:
        batch: MedicineBatch = row["batch"]
        unit_cost = Decimal(row.get("unit_cost") or batch.unit_cost or 0)
        StockAdjustmentItem.objects.create(
            adjustment=adjustment,
            medicine=row["medicine"],
            batch=batch,
            qty=Decimal(row["qty"]),
            pool=row.get("pool") or StockPool.SALEABLE,
            target_pool=row.get("target_pool"),
            unit_cost=unit_cost,
        )
        total_value += Decimal(row["qty"]) * unit_cost

    adjustment.total_value = total_value.quantize(Decimal("0.01"))
    from apps.common.settings_service import get_threshold

    threshold = get_threshold(
        "STOCK_ADJUSTMENT_APPROVAL_THRESHOLD",
        str(getattr(settings, "STOCK_ADJUSTMENT_APPROVAL_THRESHOLD", "5000")),
    )

    if total_value > threshold:
        adjustment.status = AdjustmentStatus.PENDING_APPROVAL
        adjustment.idempotency_key = idempotency_key
        adjustment.save(update_fields=["total_value", "status", "idempotency_key", "updated_at"])
    else:
        adjustment.idempotency_key = idempotency_key
        adjustment.save(update_fields=["total_value", "idempotency_key", "updated_at"])
        _post_stock_adjustment(adjustment, actor)
    return adjustment


@transaction.atomic
def approve_stock_adjustment(*, adjustment: StockAdjustment, actor, idempotency_key: str | None = None) -> StockAdjustment:
    adjustment = StockAdjustment.objects.select_for_update().get(id=adjustment.id)
    if idempotency_key and adjustment.idempotency_key == idempotency_key:
        return adjustment
    if adjustment.status != AdjustmentStatus.PENDING_APPROVAL:
        raise APIError("INVALID_STATUS_TRANSITION", "Only pending adjustments can be approved.")
    if actor.id == adjustment.requested_by_id:
        raise APIError(
            "SELF_APPROVAL_NOT_ALLOWED",
            "The requester cannot approve their own adjustment (dual control).",
            status_code=403,
        )
    adjustment.approved_by = actor
    adjustment.approved_at = timezone.now()
    adjustment.idempotency_key = idempotency_key or adjustment.idempotency_key
    adjustment.save(update_fields=["approved_by", "approved_at", "idempotency_key", "updated_at"])
    _post_stock_adjustment(adjustment, actor)
    return adjustment


@transaction.atomic
def reject_stock_adjustment(
    *, adjustment: StockAdjustment, actor, reason: str = ""
) -> StockAdjustment:
    adjustment = StockAdjustment.objects.select_for_update().get(id=adjustment.id)
    if adjustment.status != AdjustmentStatus.PENDING_APPROVAL:
        raise APIError("INVALID_STATUS_TRANSITION", "Only pending adjustments can be rejected.")
    if actor.id == adjustment.requested_by_id:
        raise APIError(
            "SELF_APPROVAL_NOT_ALLOWED",
            "The requester cannot reject their own adjustment (dual control).",
            status_code=403,
        )
    adjustment.status = AdjustmentStatus.REJECTED
    adjustment.rejection_reason = reason
    adjustment.approved_by = actor
    adjustment.approved_at = timezone.now()
    adjustment.save(update_fields=["status", "rejection_reason", "approved_by", "approved_at", "updated_at"])
    return adjustment


@transaction.atomic
def reverse_stock_adjustment(
    *, adjustment: StockAdjustment, actor, reason: str = "", idempotency_key: str | None = None
) -> StockAdjustment:
    adjustment = StockAdjustment.objects.select_for_update().get(id=adjustment.id)
    if idempotency_key and adjustment.idempotency_key == idempotency_key:
        return adjustment
    if adjustment.status != AdjustmentStatus.POSTED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only posted adjustments can be reversed.")

    reversal_lines: list[MovementLine] = []
    for item in adjustment.items.select_related("medicine", "batch"):
        sign = Decimal("-1") if adjustment.adjustment_type == "INCREASE" else Decimal("1")
        reversal_lines.append(
            MovementLine(
                medicine=item.medicine,
                batch=item.batch,
                qty_delta=sign * item.qty,
                unit_cost=item.unit_cost,
                pool=item.pool,
            )
        )
        if adjustment.adjustment_type == "DECREASE" and item.target_pool:
            reversal_lines.append(
                MovementLine(
                    medicine=item.medicine,
                    batch=item.batch,
                    qty_delta=-item.qty,
                    unit_cost=item.unit_cost,
                    pool=item.target_pool,
                )
            )

    post_transactions(
        branch=adjustment.branch,
        lines=reversal_lines,
        entry_type=EntryType.REVERSAL,
        source_type="STOCK_ADJUSTMENT_REVERSAL",
        source_id=adjustment.id,
        source_number=adjustment.number or "",
        business_date=timezone.localdate(),
        actor=actor,
    )
    adjustment.status = AdjustmentStatus.REVERSED
    adjustment.notes = (adjustment.notes + f"\nReversed: {reason}").strip()
    adjustment.idempotency_key = idempotency_key or adjustment.idempotency_key
    adjustment.save(update_fields=["status", "notes", "idempotency_key", "updated_at"])
    return adjustment
