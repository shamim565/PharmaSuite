"""Tests for delivery challans: lifecycle and invoice fulfillment linkage."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.sales.delivery_models import ChallanStatus
from apps.sales.delivery_services import (
    cancel_delivery_challan,
    complete_delivery_challan,
    create_challan_from_invoice,
    create_delivery_challan,
    dispatch_delivery_challan,
    mark_undelivered_challan,
)
from apps.sales.models import SalesInvoice, SalesInvoiceItem
from apps.sales.services import confirm_sale

pytestmark = pytest.mark.django_db


def _confirmed_invoice(branch, customer, medicine, batch, qty="5"):
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
        batch_number=batch.batch_number,
        qty=Decimal(qty),
        unit_price=Decimal("12.0000"),
        vat_rate=Decimal("0"),
        vat_amount=Decimal("0"),
    )
    return invoice


def test_challan_lifecycle_marks_invoice_delivered(branch, customer, medicine, batch, actor, stock_in):
    stock_in(batch, "10")
    invoice = _confirmed_invoice(branch, customer, medicine, batch)
    invoice = confirm_sale(invoice=invoice, actor=actor)

    challan = create_challan_from_invoice(invoice=invoice, actor=actor)
    assert challan.status == ChallanStatus.PREPARED
    assert challan.items.count() == 1

    challan = dispatch_delivery_challan(challan=challan, actor=actor)
    assert challan.status == ChallanStatus.DISPATCHED

    challan = complete_delivery_challan(
        challan=challan, actor=actor, recipient_name="Rahim", recipient_phone="01700000009"
    )
    assert challan.status == ChallanStatus.DELIVERED
    assert challan.recipient_name == "Rahim"

    invoice.refresh_from_db()
    assert invoice.fulfillment_status == "DELIVERED"


def test_undelivered_requires_dispatch(branch, customer, medicine, actor):
    challan = create_delivery_challan(
        branch=branch,
        customer=customer,
        business_date=timezone.localdate(),
        items=[{"medicine": medicine, "qty": Decimal("1")}],
        actor=actor,
    )
    with pytest.raises(APIError):
        mark_undelivered_challan(challan=challan, actor=actor)


def test_delivered_challan_cannot_be_cancelled(branch, customer, medicine, actor):
    challan = create_delivery_challan(
        branch=branch,
        customer=customer,
        business_date=timezone.localdate(),
        items=[{"medicine": medicine, "qty": Decimal("1")}],
        actor=actor,
    )
    complete_delivery_challan(challan=challan, actor=actor)

    with pytest.raises(APIError):
        cancel_delivery_challan(challan=challan, actor=actor)
