"""Tests for purchase confirm / cancel / return stock effects."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.catalog.models import MedicineBatch
from apps.common.exceptions import APIError
from apps.inventory.models import EntryType, StockBalance
from apps.inventory.services import MovementLine, post_transactions
from apps.purchases.models import (
    Purchase,
    PurchaseItem,
    PurchaseReturn,
    PurchaseReturnDocStatus,
    PurchaseReturnItem,
    PurchaseStatus,
)
from apps.purchases.services import (
    cancel_purchase,
    confirm_purchase,
    confirm_purchase_return,
)
from apps.suppliers.models import SupplierLedgerEntry, SupplierLedgerEntryType

pytestmark = pytest.mark.django_db


def _draft_purchase(branch, supplier, medicine, qty="10", unit_cost="10.0000", invoice_number=None):
    qty = Decimal(qty)
    unit_cost = Decimal(unit_cost)
    purchase = Purchase.objects.create(
        branch=branch,
        supplier=supplier,
        supplier_invoice_number=invoice_number or f"SI-{uuid4().hex[:8]}",
        supplier_invoice_date=timezone.localdate(),
        business_date=timezone.localdate(),
    )
    item = PurchaseItem.objects.create(
        purchase=purchase,
        line_no=1,
        medicine=medicine,
        batch_number=f"PB-{uuid4().hex[:4]}",
        expiry_date=timezone.localdate() + timedelta(days=365),
        qty_entered=qty,
        qty_base=qty,
        unit_cost=unit_cost,
        base_unit_cost=unit_cost,
        effective_unit_cost=unit_cost,
    )
    purchase.subtotal = qty * unit_cost
    purchase.grand_total = purchase.subtotal
    purchase.save(update_fields=["subtotal", "grand_total", "updated_at"])
    return purchase, item


def test_confirm_purchase_posts_stock_and_supplier_ledger(branch, supplier, medicine, actor):
    purchase, item = _draft_purchase(branch, supplier, medicine)

    confirmed = confirm_purchase(purchase=purchase, actor=actor)

    assert confirmed.lifecycle == PurchaseStatus.CONFIRMED
    assert confirmed.number and confirmed.number.startswith("PUR-MAIN-")

    item.refresh_from_db()
    assert item.batch is not None
    assert item.batch.qty_on_hand == Decimal("10")
    assert StockBalance.objects.get(batch=item.batch).qty_on_hand == Decimal("10")

    ledger = SupplierLedgerEntry.objects.get(entry_type=SupplierLedgerEntryType.PURCHASE)
    assert ledger.amount_delta == Decimal("100.00")
    assert ledger.source_id == confirmed.id

    batch = MedicineBatch.objects.get(id=item.batch_id)
    assert batch.qty_received_total == Decimal("10")


def test_confirm_purchase_rejects_duplicate_supplier_invoice(branch, supplier, medicine, actor):
    purchase, _ = _draft_purchase(branch, supplier, medicine, invoice_number="DUP-1")
    confirm_purchase(purchase=purchase, actor=actor)

    duplicate, _ = _draft_purchase(branch, supplier, medicine, invoice_number="DUP-1")
    with pytest.raises(APIError) as exc:
        confirm_purchase(purchase=duplicate, actor=actor)
    assert exc.value.code == "DUPLICATE_SUPPLIER_INVOICE"
    assert exc.value.status_code == 409


def test_cancel_purchase_reverses_stock_and_ledger(branch, supplier, medicine, actor):
    purchase, item = _draft_purchase(branch, supplier, medicine)
    confirm_purchase(purchase=purchase, actor=actor)
    item.refresh_from_db()

    cancelled = cancel_purchase(purchase=purchase, actor=actor, reason="wrong invoice")

    assert cancelled.lifecycle == PurchaseStatus.CANCELLED
    assert StockBalance.objects.get(batch=item.batch).qty_on_hand == Decimal("0")

    entries = list(SupplierLedgerEntry.objects.order_by("created_at"))
    assert [entry.entry_type for entry in entries] == [
        SupplierLedgerEntryType.PURCHASE,
        SupplierLedgerEntryType.ADJUSTMENT,
    ]
    assert entries[0].amount_delta == Decimal("100.00")
    assert entries[1].amount_delta == Decimal("-100.00")


def test_cancel_purchase_blocked_when_stock_consumed(branch, supplier, medicine, actor):
    purchase, item = _draft_purchase(branch, supplier, medicine)
    confirm_purchase(purchase=purchase, actor=actor)
    item.refresh_from_db()

    post_transactions(
        branch=branch,
        lines=[
            MovementLine(
                medicine=medicine,
                batch=item.batch,
                qty_delta=Decimal("-5"),
                unit_cost=item.batch.unit_cost,
            )
        ],
        entry_type=EntryType.SALE,
        business_date=timezone.localdate(),
        actor=actor,
    )

    with pytest.raises(APIError) as exc:
        cancel_purchase(purchase=purchase, actor=actor, reason="too late")
    assert exc.value.code == "PURCHASE_STOCK_CONSUMED"
    assert exc.value.status_code == 409
    assert StockBalance.objects.get(batch=item.batch).qty_on_hand == Decimal("5")


def test_purchase_return_decrements_stock_and_ledger(branch, supplier, medicine, actor):
    purchase, item = _draft_purchase(branch, supplier, medicine)
    confirm_purchase(purchase=purchase, actor=actor)
    item.refresh_from_db()

    purchase_return = PurchaseReturn.objects.create(
        purchase=purchase,
        supplier=supplier,
        branch=branch,
        business_date=timezone.localdate(),
        reason_code="DAMAGED",
    )
    PurchaseReturnItem.objects.create(
        purchase_return=purchase_return,
        purchase_item=item,
        batch=item.batch,
        qty=Decimal("4"),
    )

    confirmed_return = confirm_purchase_return(purchase_return=purchase_return, actor=actor)

    assert confirmed_return.status == PurchaseReturnDocStatus.CONFIRMED
    assert confirmed_return.number and confirmed_return.number.startswith("DBN-MAIN-")
    assert StockBalance.objects.get(batch=item.batch).qty_on_hand == Decimal("6")

    item.refresh_from_db()
    assert item.returned_qty_base == Decimal("4")

    ledger = SupplierLedgerEntry.objects.get(entry_type=SupplierLedgerEntryType.PURCHASE_RETURN)
    assert ledger.amount_delta == Decimal("-40.00")


def test_purchase_return_cannot_exceed_returnable(branch, supplier, medicine, actor):
    purchase, item = _draft_purchase(branch, supplier, medicine)
    confirm_purchase(purchase=purchase, actor=actor)
    item.refresh_from_db()

    purchase_return = PurchaseReturn.objects.create(
        purchase=purchase,
        supplier=supplier,
        branch=branch,
        business_date=timezone.localdate(),
        reason_code="DAMAGED",
    )
    PurchaseReturnItem.objects.create(
        purchase_return=purchase_return,
        purchase_item=item,
        batch=item.batch,
        qty=Decimal("11"),
    )

    with pytest.raises(APIError) as exc:
        confirm_purchase_return(purchase_return=purchase_return, actor=actor)
    assert exc.value.code == "RETURN_EXCEEDS_PURCHASE"
    assert StockBalance.objects.get(batch=item.batch).qty_on_hand == Decimal("10")
