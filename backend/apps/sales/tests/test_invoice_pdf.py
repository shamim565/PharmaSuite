"""Invoice PDF rendering endpoint."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.sales.models import SalesInvoice, SalesInvoiceItem
from apps.sales.services import confirm_sale

pytestmark = pytest.mark.django_db


def _confirmed_invoice(branch, customer, medicine, batch, stock_in, actor):
    stock_in(batch, "10")
    invoice = SalesInvoice.objects.create(
        branch=branch, customer=customer, business_date=timezone.localdate()
    )
    SalesInvoiceItem.objects.create(
        invoice=invoice,
        line_no=1,
        medicine=medicine,
        qty=Decimal("2"),
        unit_price=Decimal("12.0000"),
        vat_rate=Decimal("15"),
        vat_amount=Decimal("0"),
    )
    return confirm_sale(invoice=invoice, actor=actor)


def test_invoice_pdf_download(branch, customer, medicine, batch, stock_in, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    invoice = _confirmed_invoice(branch, customer, medicine, batch, stock_in, actor)

    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/sales/{invoice.id}/print/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response["Content-Disposition"]


def test_invoice_pdf_requires_sale_view(branch, customer, medicine, batch, stock_in, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    invoice = _confirmed_invoice(branch, customer, medicine, batch, stock_in, actor)

    grant_role(actor, ["USER_VIEW"], branch_scope=BranchScope.ALL)
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/sales/{invoice.id}/print/")

    assert response.status_code == 403
