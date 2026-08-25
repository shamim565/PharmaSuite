"""The stock movement report relies on business-date range filters on transactions."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    return client


def test_transactions_date_range_filter(api, batch, stock_in):
    today = timezone.localdate()
    yesterday = today.fromordinal(today.toordinal() - 1)
    stock_in(batch, "5", business_date=yesterday)
    stock_in(batch, "3", business_date=today)

    all_rows = api.get("/api/v1/inventory/transactions/?page_size=50").json()
    assert all_rows["count"] == 2

    today_only = api.get(
        f"/api/v1/inventory/transactions/?date_from={today.isoformat()}&date_to={today.isoformat()}"
    ).json()
    assert today_only["count"] == 1
    assert today_only["results"][0]["qty_delta"] == "3.000"

    yesterday_upto = api.get(
        f"/api/v1/inventory/transactions/?date_to={yesterday.isoformat()}"
    ).json()
    assert yesterday_upto["count"] == 1
    assert Decimal(yesterday_upto["results"][0]["qty_delta"]) == Decimal("5.000")
