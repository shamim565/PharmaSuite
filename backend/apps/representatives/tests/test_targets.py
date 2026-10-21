"""Tests for monthly sales targets."""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.representatives.models import Representative, SalesTarget
from apps.representatives.serializers import SalesTargetSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture
def rep(db):
    return Representative.objects.create(code="REP-001", name="Karim", rep_type="SALES")


def test_target_unique_per_rep_period(rep):
    today = timezone.localdate()
    SalesTarget.objects.create(
        representative=rep,
        fiscal_year=today.year,
        period_month=today.month,
        target_amount=Decimal("100000.00"),
    )
    with pytest.raises(IntegrityError):
        SalesTarget.objects.create(
            representative=rep,
            fiscal_year=today.year,
            period_month=today.month,
            target_amount=Decimal("200000.00"),
        )


def test_target_achievement_defaults_to_zero_without_sales(rep):
    today = timezone.localdate()
    target = SalesTarget.objects.create(
        representative=rep,
        fiscal_year=today.year,
        period_month=today.month,
        target_amount=Decimal("100000.00"),
    )
    data = SalesTargetSerializer(target).data
    assert Decimal(data["achieved_sales"]) == Decimal("0")
    assert data["achieved_percent"] == 0.0
