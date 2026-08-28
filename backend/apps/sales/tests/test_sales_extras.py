"""Draft delete, register date filter, and the sales config endpoint."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.common.settings_service import set_setting_value
from apps.sales.models import SalesInvoice

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _invoice(branch, customer, *, business_date=None, number=None, lifecycle="DRAFT"):
    return SalesInvoice.objects.create(
        branch=branch,
        customer=customer,
        business_date=business_date or timezone.localdate(),
        number=number,
        lifecycle=lifecycle,
    )


def test_draft_can_be_deleted(branch, customer, actor):
    grant_role(actor, ["SALE_CREATE"], branch_scope=BranchScope.ALL)
    invoice = _invoice(branch, customer)

    response = _client(actor).delete(f"/api/v1/sales/{invoice.id}/")

    assert response.status_code == 204
    assert not SalesInvoice.objects.filter(id=invoice.id).exists()


def test_confirmed_invoice_cannot_be_deleted(branch, customer, actor):
    grant_role(actor, ["SALE_CREATE"], branch_scope=BranchScope.ALL)
    invoice = _invoice(branch, customer, number="INV-MAIN-26-000001", lifecycle="CONFIRMED")

    response = _client(actor).delete(f"/api/v1/sales/{invoice.id}/")

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_STATUS_TRANSITION"
    assert SalesInvoice.objects.filter(id=invoice.id).exists()


def test_due_list_pagination(branch, customer, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    today = timezone.localdate()
    for index in range(2):
        _invoice(
            branch,
            customer,
            lifecycle="CONFIRMED",
            number=f"INV-MAIN-26-10000{index}",
        )
    SalesInvoice.objects.filter(branch=branch).update(
        grand_total=Decimal("100.00"), paid_total=Decimal("0.00"), due_date=today
    )

    first = _client(actor).get("/api/v1/sales/due-list/?page_size=1&page=1")
    assert first.status_code == 200
    body = first.json()
    assert body["count"] == 2
    assert len(body["results"]) == 1
    assert body["next"] is True
    assert body["previous"] is False

    second = _client(actor).get("/api/v1/sales/due-list/?page_size=1&page=2")
    body = second.json()
    assert len(body["results"]) == 1
    assert body["next"] is False
    assert body["previous"] is True


def test_register_date_filter(branch, customer, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    today = timezone.localdate()
    old_invoice = _invoice(branch, customer, business_date=today - timedelta(days=10))
    new_invoice = _invoice(branch, customer, business_date=today)

    response = _client(actor).get(
        f"/api/v1/sales/?date_from={(today - timedelta(days=1)).isoformat()}"
    )

    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["results"]}
    assert {str(new_invoice.id)} == ids
    assert str(old_invoice.id) not in ids


def test_sales_config_reports_vat_flag(branch, actor):
    grant_role(actor, ["SALE_VIEW"], branch_scope=BranchScope.ALL)

    response = _client(actor).get("/api/v1/sales/config/")
    assert response.status_code == 200
    assert response.json() == {"vat_enabled": False}

    set_setting_value("SALES_VAT_ENABLED", True)
    response = _client(actor).get("/api/v1/sales/config/")
    assert response.json() == {"vat_enabled": True}
