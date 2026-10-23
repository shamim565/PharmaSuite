"""Tests for the stock-adjustment approval workflow (dual control)."""

from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.inventory.models import (
    AdjustmentStatus,
    InventoryTransaction,
    StockAdjustment,
    StockBalance,
    StockPool,
)
from apps.inventory.services import (
    approve_stock_adjustment,
    create_stock_adjustment,
    reject_stock_adjustment,
    reverse_stock_adjustment,
)

pytestmark = pytest.mark.django_db


def _item(batch, qty, **extra):
    return {
        "medicine": batch.medicine,
        "batch": batch,
        "qty": Decimal(str(qty)),
        "unit_cost": batch.unit_cost,
        **extra,
    }


def test_small_decrease_auto_posts(branch, batch, actor, stock_in):
    stock_in(batch, "10")

    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 4)],
        actor=actor,
    )

    assert adjustment.status == AdjustmentStatus.POSTED
    assert adjustment.number and adjustment.number.startswith("ADJ-MAIN-")
    assert adjustment.total_value == Decimal("40.00")
    assert StockBalance.objects.get().qty_on_hand == Decimal("6")

    txn = InventoryTransaction.objects.get(entry_type="DAMAGE")
    assert txn.qty_delta == Decimal("-4")
    assert txn.source_type == "STOCK_ADJUSTMENT"
    assert txn.source_id == adjustment.id


def test_large_adjustment_requires_dual_control(branch, batch, actor, approver, stock_in):
    stock_in(batch, "2000")

    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="EXPIRY_WRITE_OFF",
        items_data=[_item(batch, 1000)],
        actor=actor,
    )

    assert adjustment.status == AdjustmentStatus.PENDING_APPROVAL
    assert adjustment.number is None
    assert StockBalance.objects.get().qty_on_hand == Decimal("2000")

    with pytest.raises(APIError) as exc:
        approve_stock_adjustment(adjustment=adjustment, actor=actor)
    assert exc.value.code == "SELF_APPROVAL_NOT_ALLOWED"
    assert exc.value.status_code == 403

    with pytest.raises(APIError):
        reject_stock_adjustment(adjustment=adjustment, actor=actor)

    approved = approve_stock_adjustment(adjustment=adjustment, actor=approver)
    approved.refresh_from_db()
    assert approved.status == AdjustmentStatus.POSTED
    assert approved.approved_by == approver
    assert approved.number and approved.number.startswith("ADJ-MAIN-")


def test_approve_rejected_when_already_posted(branch, batch, actor, approver, stock_in):
    stock_in(batch, "10")
    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 2)],
        actor=actor,
    )
    assert adjustment.status == AdjustmentStatus.POSTED
    with pytest.raises(APIError) as exc:
        approve_stock_adjustment(adjustment=adjustment, actor=approver)
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


def test_reject_keeps_stock_untouched(branch, batch, actor, approver, stock_in):
    stock_in(batch, "100")
    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 1000)],
        actor=actor,
    )

    rejected = reject_stock_adjustment(adjustment=adjustment, actor=approver, reason="no evidence")
    rejected.refresh_from_db()
    assert rejected.status == AdjustmentStatus.REJECTED
    assert rejected.rejection_reason == "no evidence"
    assert StockBalance.objects.get().qty_on_hand == Decimal("100")
    assert InventoryTransaction.objects.count() == 1  # only the stock-in


def test_reverse_restores_stock(branch, batch, actor, stock_in):
    stock_in(batch, "10")
    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 4)],
        actor=actor,
    )
    assert StockBalance.objects.get().qty_on_hand == Decimal("6")

    reversed_adjustment = reverse_stock_adjustment(
        adjustment=adjustment, actor=actor, reason="counted again"
    )
    reversed_adjustment.refresh_from_db()
    assert reversed_adjustment.status == AdjustmentStatus.REVERSED
    assert StockBalance.objects.get().qty_on_hand == Decimal("10")

    reversal = InventoryTransaction.objects.get(entry_type="REVERSAL")
    assert reversal.qty_delta == Decimal("4")

    with pytest.raises(APIError) as exc:
        reverse_stock_adjustment(adjustment=reversed_adjustment, actor=actor)
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


def test_move_between_pools(branch, batch, actor, stock_in):
    stock_in(batch, "10")
    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DATA_CORRECTION",
        items_data=[_item(batch, 3, pool=StockPool.SALEABLE, target_pool=StockPool.QUARANTINE)],
        actor=actor,
    )
    assert adjustment.status == AdjustmentStatus.POSTED

    balance = StockBalance.objects.get()
    assert balance.qty_on_hand == Decimal("7")
    assert balance.qty_quarantine == Decimal("3")


def test_duplicate_idempotency_key_returns_same_adjustment(branch, batch, actor, stock_in):
    stock_in(batch, "10")
    first = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 1)],
        actor=actor,
        idempotency_key="adj-key-1",
    )
    second = create_stock_adjustment(
        branch=branch,
        adjustment_type="DECREASE",
        reason_code="DAMAGE",
        items_data=[_item(batch, 1)],
        actor=actor,
        idempotency_key="adj-key-1",
    )
    assert first.id == second.id
    assert StockAdjustment.objects.count() == 1
    assert StockBalance.objects.get().qty_on_hand == Decimal("9")


def test_increase_posts_positive_stock(branch, batch, actor):
    adjustment = create_stock_adjustment(
        branch=branch,
        adjustment_type="INCREASE",
        reason_code="FOUND_STOCK",
        items_data=[_item(batch, 7)],
        actor=actor,
        business_date=timezone.localdate(),
    )
    assert adjustment.status == AdjustmentStatus.POSTED
    assert StockBalance.objects.get().qty_on_hand == Decimal("7")


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Concurrency semantics require PostgreSQL row locking (SQLite locks the whole table).",
)
def test_concurrent_same_key_creates_one_adjustment(branch, batch, actor, stock_in):
    import threading

    from django.db import connection

    stock_in(batch, "10")
    barrier = threading.Barrier(2)
    results = []
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait(timeout=10)
            results.append(
                create_stock_adjustment(
                    branch=branch,
                    adjustment_type="DECREASE",
                    reason_code="DAMAGE",
                    items_data=[_item(batch, 1)],
                    actor=actor,
                    idempotency_key="race-key-adjustment",
                )
            )
        except Exception as exc:  # pragma: no cover - failure diagnostics
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(results) == 2
    assert results[0].id == results[1].id
    assert StockAdjustment.objects.count() == 1
    assert InventoryTransaction.objects.filter(entry_type="DAMAGE").count() == 1
