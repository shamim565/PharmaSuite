"""Tests for FEFO allocation and sale confirmation."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.inventory.models import StockBalance
from apps.sales.models import (
    CustomerLedgerEntry,
    SalesInvoice,
    SalesInvoiceItem,
    SalesInvoiceStatus,
)
from apps.sales.services import confirm_sale, fefo_allocate, fefo_candidates

pytestmark = pytest.mark.django_db


def _draft_invoice(branch, customer, medicine, qty, unit_price="12.0000", batch=None):
    invoice = SalesInvoice.objects.create(
        branch=branch,
        customer=customer,
        business_date=timezone.localdate(),
    )
    SalesInvoiceItem.objects.create(
        invoice=invoice,
        line_no=1,
        medicine=medicine,
        batch=batch,
        qty=Decimal(str(qty)),
        unit_price=Decimal(unit_price),
        vat_rate=Decimal("15"),
        vat_amount=Decimal("0"),
    )
    return invoice


def test_fefo_allocates_earliest_expiry_first(branch, medicine, make_batch, stock_in):
    later = make_batch(batch_number="LATER", days_to_expiry=300)
    sooner = make_batch(batch_number="SOONER", days_to_expiry=30)
    stock_in(later, "10")
    stock_in(sooner, "10")

    allocations = fefo_allocate(branch, medicine, Decimal("6"))

    assert len(allocations) == 1
    assert allocations[0][0] == sooner
    assert allocations[0][1] == Decimal("6")


def test_fefo_splits_across_batches_and_excludes_expired(branch, medicine, make_batch, stock_in):
    sooner = make_batch(batch_number="SOONER", days_to_expiry=30)
    later = make_batch(batch_number="LATER", days_to_expiry=300)
    expired = make_batch(batch_number="EXPIRED", days_to_expiry=-5)
    stock_in(sooner, "3")
    stock_in(later, "10")
    stock_in(expired, "100")

    allocations = fefo_allocate(branch, medicine, Decimal("8"))

    assert [(batch.batch_number, take) for batch, take in allocations] == [
        ("SOONER", Decimal("3")),
        ("LATER", Decimal("5")),
    ]

    candidates = fefo_candidates(branch, medicine)
    assert [row["batch_number"] for row in candidates] == ["SOONER", "LATER"]


def test_fefo_reads_balance_not_stale_batch_cache(branch, medicine, make_batch, stock_in):
    batch = make_batch()
    stock_in(batch, "10")

    # Simulate a drifted display-only batch cache: FEFO must trust StockBalance.
    batch.qty_on_hand = Decimal("1")
    batch.save(update_fields=["qty_on_hand", "updated_at"])

    allocations = fefo_allocate(branch, medicine, Decimal("8"))
    assert [(row[0].batch_number, row[1]) for row in allocations] == [("B1", Decimal("8"))]

    candidates = fefo_candidates(branch, medicine)
    assert candidates[0]["qty_on_hand"] == Decimal("10")


def test_fefo_raises_when_insufficient(branch, medicine, make_batch, stock_in):
    batch = make_batch()
    stock_in(batch, "2")

    with pytest.raises(APIError) as exc:
        fefo_allocate(branch, medicine, Decimal("5"))
    assert exc.value.code == "INSUFFICIENT_STOCK"
    assert exc.value.status_code == 409


def test_confirm_sale_deducts_stock_numbers_and_posts_receivable(
    branch, customer, actor, medicine, batch, stock_in
):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 4)

    confirmed = confirm_sale(invoice=invoice, actor=actor)

    assert confirmed.lifecycle == SalesInvoiceStatus.CONFIRMED
    assert confirmed.number and confirmed.number.startswith("INV-MAIN-")
    assert confirmed.grand_total == Decimal("48.00")  # 4 × 12.00, VAT captured on the draft item

    balance = StockBalance.objects.get(branch=branch, medicine=medicine, batch=batch)
    assert balance.qty_on_hand == Decimal("6")

    ledger = CustomerLedgerEntry.objects.get(entry_type="INVOICE")
    assert ledger.amount_delta == confirmed.grand_total
    assert ledger.source_id == confirmed.id

    item = confirmed.items.get()
    assert item.batch == batch
    assert item.unit_cost == batch.unit_cost
    customer.refresh_from_db()
    assert customer.balance_cache == confirmed.grand_total


def test_confirm_sale_splits_lines_across_batches(
    branch, customer, actor, medicine, make_batch, stock_in
):
    sooner = make_batch(batch_number="SOONER", days_to_expiry=30)
    later = make_batch(batch_number="LATER", days_to_expiry=300)
    stock_in(sooner, "3")
    stock_in(later, "5")
    invoice = _draft_invoice(branch, customer, medicine, 6)

    confirmed = confirm_sale(invoice=invoice, actor=actor)

    lines = list(confirmed.items.order_by("line_no"))
    assert [(line.batch.batch_number, line.qty) for line in lines] == [
        ("SOONER", Decimal("3")),
        ("LATER", Decimal("3")),
    ]
    assert StockBalance.objects.get(batch=sooner).qty_on_hand == Decimal("0")
    assert StockBalance.objects.get(batch=later).qty_on_hand == Decimal("2")


def test_explicit_batch_override_uses_selected_batch(
    branch, customer, actor, medicine, make_batch, stock_in
):
    sooner = make_batch(batch_number="SOONER", days_to_expiry=30)
    later = make_batch(batch_number="LATER", days_to_expiry=300)
    stock_in(sooner, "10")
    stock_in(later, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, batch=later)

    confirm_sale(invoice=invoice, actor=actor)

    assert StockBalance.objects.get(batch=sooner).qty_on_hand == Decimal("10")
    assert StockBalance.objects.get(batch=later).qty_on_hand == Decimal("8")


def test_confirm_sale_insufficient_rolls_back(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "3")
    invoice = _draft_invoice(branch, customer, medicine, 10)

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert exc.value.code == "INSUFFICIENT_STOCK"

    invoice.refresh_from_db()
    assert invoice.lifecycle == SalesInvoiceStatus.DRAFT
    assert invoice.number is None
    assert invoice.items.count() == 1
    assert CustomerLedgerEntry.objects.count() == 0
    assert StockBalance.objects.get().qty_on_hand == Decimal("3")


def test_sale_of_expired_batch_not_sellable(branch, customer, actor, medicine, make_batch, stock_in):
    expired = make_batch(batch_number="OLD", days_to_expiry=-1)
    stock_in(expired, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2)

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert exc.value.code == "INSUFFICIENT_STOCK"


def test_confirm_sale_is_idempotent(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2)

    first = confirm_sale(invoice=invoice, actor=actor, idempotency_key="sale-key-1")
    second = confirm_sale(invoice=invoice, actor=actor, idempotency_key="sale-key-1")

    assert first.id == second.id
    assert StockBalance.objects.get().qty_on_hand == Decimal("8")
    assert CustomerLedgerEntry.objects.count() == 1


def test_credit_hold_blocks_sale(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    customer.credit_hold = True
    customer.save(update_fields=["credit_hold"])
    invoice = _draft_invoice(branch, customer, medicine, 1)

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert exc.value.code == "CUSTOMER_ON_HOLD"

    invoice.refresh_from_db()
    assert invoice.lifecycle == SalesInvoiceStatus.DRAFT
