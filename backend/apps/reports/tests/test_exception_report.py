"""API tests for the exception / override report (zero value, below cost, overrides)."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sales.models import SalesInvoice, SalesInvoiceItem
from apps.sales.services import confirm_sale

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    return client


def _invoice(branch, customer, medicine, batch, qty, unit_price):
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
        unit_price=Decimal(unit_price),
        vat_rate=Decimal("0"),
        vat_amount=Decimal("0"),
    )
    return invoice


def test_exception_report_flags_zero_value_and_below_cost(
    api, branch, customer, medicine, make_batch, actor, stock_in
):
    batch = make_batch(batch_number="EX-1", unit_cost="10.0000")
    stock_in(batch, "20")

    zero = _invoice(branch, customer, medicine, batch, "1", "0")
    confirm_sale(invoice=zero, actor=actor)

    below = _invoice(branch, customer, medicine, batch, "1", "5")
    confirm_sale(invoice=below, actor=actor)

    response = api.get("/api/v1/reports/exceptions/")
    assert response.status_code == 200
    data = response.json()

    types = {override["type"] for row in data["results"] for override in row["overrides"]}
    assert "ZERO_VALUE" in types
    assert "BELOW_COST" in types
    assert data["invoice_exceptions"] >= 2

    by_type = api.get("/api/v1/reports/exceptions/?override_type=ZERO_VALUE")
    assert by_type.status_code == 200
    assert by_type.json()["total_exceptions"] == 1
