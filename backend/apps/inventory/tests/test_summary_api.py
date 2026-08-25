"""API tests for the stock summary / low-stock report push-down filtering."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Medicine, MedicineBatch

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    return client


@pytest.fixture
def second_medicine(db):
    return Medicine.objects.create(
        code="MED-002",
        name="Amoxicillin 250mg",
        purchase_price=Decimal("5.00"),
        selling_price=Decimal("7.00"),
        mrp=Decimal("8.00"),
        reorder_level=Decimal("20.000"),
    )


def _summary(api, query=""):
    response = api.get(f"/api/v1/inventory/summary/{query}")
    assert response.status_code == 200
    return response.json()


def _stock_second(branch, second_medicine, stock_in, qty):
    batch = MedicineBatch.objects.create(
        branch=branch,
        medicine=second_medicine,
        batch_number="B2",
        expiry_date=timezone.localdate() + timedelta(days=365),
        unit_cost=Decimal("5.0000"),
    )
    stock_in(batch, qty)
    return batch


def test_summary_search_filters_rows(
    api, branch, medicine, second_medicine, batch, stock_in
):
    stock_in(batch, "100")
    _stock_second(branch, second_medicine, stock_in, "50")

    payload = _summary(api, "?search=amox")

    assert payload["count"] == 1
    assert payload["results"][0]["medicine_code"] == "MED-002"


def test_low_stock_report_returns_only_low_rows(
    api, branch, medicine, second_medicine, batch, stock_in
):
    # Paracetamol has reorder_level 5 and on-hand 3 => low.
    stock_in(batch, "3")
    _stock_second(branch, second_medicine, stock_in, "50")

    response = api.get("/api/v1/inventory/reports/low-stock/")
    assert response.status_code == 200
    payload = response.json()

    assert payload["count"] == 1
    assert payload["results"][0]["medicine_code"] == "MED-001"
    assert payload["results"][0]["is_low_stock"] is True


def test_summary_low_stock_param_filters_in_sql(
    api, branch, medicine, second_medicine, batch, stock_in
):
    stock_in(batch, "3")
    _stock_second(branch, second_medicine, stock_in, "50")

    payload = _summary(api, "?low_stock=true")

    assert payload["count"] == 1
    assert payload["results"][0]["medicine_code"] == "MED-001"


def test_summary_optional_pagination(
    api, branch, medicine, second_medicine, batch, stock_in
):
    stock_in(batch, "100")
    _stock_second(branch, second_medicine, stock_in, "50")

    first_page = _summary(api, "?page_size=1&page=1")
    assert first_page["count"] == 2
    assert len(first_page["results"]) == 1
    assert first_page["next"] is True
    assert first_page["previous"] is False

    second_page = _summary(api, "?page_size=1&page=2")
    assert second_page["count"] == 2
    assert len(second_page["results"]) == 1
    assert second_page["next"] is False
    assert second_page["previous"] is True
    assert second_page["results"][0]["medicine_code"] != first_page["results"][0]["medicine_code"]
