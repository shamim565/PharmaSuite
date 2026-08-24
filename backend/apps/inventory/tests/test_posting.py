"""Tests for the inventory posting choke-point."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import BatchStatus, MedicineBatch
from apps.common.exceptions import APIError
from apps.inventory.models import (
    EntryType,
    InventoryTransaction,
    StockBalance,
    StockPool,
)
from apps.inventory.services import (
    MovementLine,
    available_quantity,
    ledger_quantities,
    post_transactions,
)

pytestmark = pytest.mark.django_db


def test_post_creates_ledger_row_and_balance(branch, batch, actor):
    post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("10"))],
        entry_type=EntryType.OPENING,
        business_date=timezone.localdate(),
        actor=actor,
    )

    txn = InventoryTransaction.objects.get()
    assert txn.qty_delta == Decimal("10")
    assert txn.entry_type == EntryType.OPENING
    assert txn.created_by == actor

    balance = StockBalance.objects.get(branch=branch, medicine=batch.medicine, batch=batch)
    assert balance.qty_on_hand == Decimal("10")

    batch.refresh_from_db()
    assert batch.qty_on_hand == Decimal("10")
    assert batch.status == BatchStatus.ACTIVE
    assert ledger_quantities(branch, batch.medicine, batch)["SALEABLE"] == Decimal("10")


def test_zero_quantity_rejected(branch, batch):
    with pytest.raises(APIError) as exc:
        post_transactions(
            branch=branch,
            lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("0"))],
            entry_type=EntryType.ADJUSTMENT,
            business_date=timezone.localdate(),
        )
    assert exc.value.code == "INVALID_QUANTITY"
    assert InventoryTransaction.objects.count() == 0


def test_insufficient_stock_rolls_back_everything(branch, batch):
    post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("5"))],
        entry_type=EntryType.OPENING,
        business_date=timezone.localdate(),
    )

    with pytest.raises(APIError) as exc:
        post_transactions(
            branch=branch,
            lines=[
                MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("-3")),
                MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("-4")),
            ],
            entry_type=EntryType.SALE,
            business_date=timezone.localdate(),
        )
    assert exc.value.code == "INSUFFICIENT_STOCK"
    assert exc.value.status_code == 409

    balance = StockBalance.objects.get()
    assert balance.qty_on_hand == Decimal("5")
    assert InventoryTransaction.objects.count() == 1


def test_pools_are_isolated(branch, batch, stock_in):
    stock_in(batch, "10")
    post_transactions(
        branch=branch,
        lines=[
            MovementLine(
                medicine=batch.medicine,
                batch=batch,
                qty_delta=Decimal("3"),
                pool=StockPool.PROMO,
            )
        ],
        entry_type=EntryType.BONUS,
        business_date=timezone.localdate(),
    )

    balance = StockBalance.objects.get()
    assert balance.qty_on_hand == Decimal("10")
    assert balance.qty_promo == Decimal("3")
    assert available_quantity(branch, batch.medicine, batch) == Decimal("10")
    assert available_quantity(branch, batch.medicine, batch, StockPool.PROMO) == Decimal("3")

    with pytest.raises(APIError):
        post_transactions(
            branch=branch,
            lines=[
                MovementLine(
                    medicine=batch.medicine,
                    batch=batch,
                    qty_delta=Decimal("-4"),
                    pool=StockPool.PROMO,
                )
            ],
            entry_type=EntryType.SALE,
            business_date=timezone.localdate(),
        )


def test_idempotency_key_returns_original_postings(branch, batch):
    first = post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("10"))],
        entry_type=EntryType.ADJUSTMENT,
        business_date=timezone.localdate(),
        idempotency_key="idem-key-1",
    )
    second = post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("10"))],
        entry_type=EntryType.ADJUSTMENT,
        business_date=timezone.localdate(),
        idempotency_key="idem-key-1",
    )

    assert [row.id for row in first] == [row.id for row in second]
    assert InventoryTransaction.objects.count() == 1
    assert StockBalance.objects.get().qty_on_hand == Decimal("10")


def test_ledger_is_append_only(branch, batch, stock_in):
    (txn,) = stock_in(batch, "10")

    txn.qty_delta = Decimal("99")
    with pytest.raises(ValueError):
        txn.save()

    with pytest.raises(ValueError):
        txn.delete()


def test_batch_flips_to_depleted_then_back(branch, batch, stock_in, actor):
    stock_in(batch, "5")
    post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=batch.medicine, batch=batch, qty_delta=Decimal("-5"))],
        entry_type=EntryType.SALE,
        business_date=timezone.localdate(),
        actor=actor,
    )
    batch.refresh_from_db()
    assert batch.status == BatchStatus.DEPLETED

    stock_in(batch, "2")
    batch.refresh_from_db()
    assert batch.status == BatchStatus.ACTIVE


def test_multi_line_locks_every_posted_batch(branch, medicine, make_batch, actor):
    batch_a = make_batch(batch_number="A", unit_cost="10")
    batch_b = make_batch(batch_number="B", unit_cost="11")
    lines = [
        MovementLine(medicine=medicine, batch=batch_b, qty_delta=Decimal("3")),
        MovementLine(medicine=medicine, batch=batch_a, qty_delta=Decimal("4")),
    ]
    post_transactions(
        branch=branch,
        lines=lines,
        entry_type=EntryType.PURCHASE,
        business_date=timezone.localdate(),
        actor=actor,
    )

    assert StockBalance.objects.count() == 2
    assert (
        StockBalance.objects.get(batch=batch_a).qty_on_hand,
        StockBalance.objects.get(batch=batch_b).qty_on_hand,
    ) == (Decimal("4"), Decimal("3"))


def test_missing_balance_row_is_created(branch, medicine, make_batch):
    batch = make_batch()
    assert MedicineBatch.objects.filter(id=batch.id).exists()
    assert StockBalance.objects.count() == 0

    post_transactions(
        branch=branch,
        lines=[MovementLine(medicine=medicine, batch=batch, qty_delta=Decimal("1"))],
        entry_type=EntryType.OPENING,
        business_date=timezone.localdate(),
    )
    assert StockBalance.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_key_posts_only_once(branch, medicine, make_batch, actor):
    import threading

    from django.db import connection

    batch = make_batch()
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait(timeout=10)
            post_transactions(
                branch=branch,
                lines=[
                    MovementLine(medicine=medicine, batch=batch, qty_delta=Decimal("10"))
                ],
                entry_type=EntryType.ADJUSTMENT,
                business_date=timezone.localdate(),
                actor=actor,
                idempotency_key="race-key-posting",
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
    assert InventoryTransaction.objects.filter(idempotency_key="race-key-posting").count() == 1
    balance = StockBalance.objects.get(branch=branch, medicine=medicine, batch=batch)
    assert balance.qty_on_hand == Decimal("10")
