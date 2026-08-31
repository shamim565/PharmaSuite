"""VAT is off by default and only applied when the setting is enabled."""

from decimal import Decimal

import pytest

from apps.common.settings_service import get_setting_bool, set_setting_value
from apps.sales.serializers import SalesInvoiceWriteSerializer

pytestmark = pytest.mark.django_db


def _draft_through_serializer(branch, customer, medicine, qty="2", unit_price="12.0000"):
    serializer = SalesInvoiceWriteSerializer(
        data={
            "customer": str(customer.id),
            "branch": str(branch.id),
            "items": [
                {"medicine": str(medicine.id), "qty": qty, "unit_price": unit_price}
            ],
        }
    )
    assert serializer.is_valid(), serializer.errors
    return serializer.save()


def test_sales_vat_disabled_by_default(branch, customer, medicine):
    invoice = _draft_through_serializer(branch, customer, medicine)

    assert invoice.vat_total == Decimal("0")
    assert invoice.grand_total == Decimal("24.00")
    assert invoice.items.get().vat_rate == Decimal("0")


def test_sales_vat_applies_when_enabled(branch, customer, medicine):
    set_setting_value("SALES_VAT_ENABLED", True)

    invoice = _draft_through_serializer(branch, customer, medicine)

    assert invoice.vat_total == Decimal("3.60")
    assert invoice.grand_total == Decimal("28.00")
    assert invoice.items.get().vat_rate == Decimal("15.00")


def test_sales_vat_per_line_override(branch, customer, medicine):
    set_setting_value("SALES_VAT_ENABLED", True)
    serializer = SalesInvoiceWriteSerializer(
        data={
            "customer": str(customer.id),
            "branch": str(branch.id),
            "items": [
                {
                    "medicine": str(medicine.id),
                    "qty": "2",
                    "unit_price": "12.0000",
                    "vat_rate": "5",
                }
            ],
        }
    )
    assert serializer.is_valid(), serializer.errors
    invoice = serializer.save()

    assert invoice.items.get().vat_rate == Decimal("5.00")
    assert invoice.vat_total == Decimal("1.20")


def test_setting_bool_coerces_ui_strings(db):
    set_setting_value("SALES_VAT_ENABLED", "false")
    assert get_setting_bool("SALES_VAT_ENABLED", default=True) is False

    set_setting_value("SALES_VAT_ENABLED", "true")
    assert get_setting_bool("SALES_VAT_ENABLED", default=False) is True

    assert get_setting_bool("UNKNOWN_KEY", default=True) is True
