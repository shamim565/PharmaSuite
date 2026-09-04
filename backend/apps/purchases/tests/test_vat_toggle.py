"""Purchase VAT is off by default and only applied when the setting is enabled."""

from decimal import Decimal

import pytest

from apps.common.settings_service import set_setting_value
from apps.purchases.services import compute_line_totals

pytestmark = pytest.mark.django_db


def _line(vat_rate=None):
    return {
        "qty_entered": "10",
        "unit_cost": "10.0000",
        "vat_rate": vat_rate,
    }


def test_purchase_vat_disabled_by_default():
    row = compute_line_totals(_line(vat_rate="15"))

    assert row["vat_rate"] == Decimal("0")
    assert row["vat_amount"] == Decimal("0")


def test_purchase_vat_applies_when_enabled():
    set_setting_value("PURCHASE_VAT_ENABLED", True)

    row = compute_line_totals(_line(vat_rate="15"))

    assert row["vat_rate"] == Decimal("15")
    assert row["vat_amount"] == Decimal("15.00")


def test_purchase_vat_default_rate_when_enabled():
    set_setting_value("PURCHASE_VAT_ENABLED", True)

    row = compute_line_totals(_line(vat_rate=None))

    assert row["vat_amount"] == Decimal("15.00")
