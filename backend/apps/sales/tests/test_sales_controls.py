"""Enforcement of sale override permissions and cancel/scope guards."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import AccountType, FinancialAccount
from apps.accounts.models import BranchScope, UserBranch
from apps.accounts.tests.helpers import grant_role
from apps.common.exceptions import APIError
from apps.inventory.models import StockBalance
from apps.sales.models import SalesInvoice, SalesInvoiceItem
from apps.sales.services import (
    cancel_sale,
    confirm_sale,
    confirm_sales_return,
    create_sales_return,
)

pytestmark = pytest.mark.django_db


def _draft_invoice(branch, customer, medicine, qty, unit_price="12.0000", free=False):
    invoice = SalesInvoice.objects.create(
        branch=branch,
        customer=customer,
        business_date=timezone.localdate(),
    )
    SalesInvoiceItem.objects.create(
        invoice=invoice,
        line_no=1,
        medicine=medicine,
        qty=Decimal(str(qty)),
        unit_price=Decimal(unit_price),
        vat_rate=Decimal("15"),
        vat_amount=Decimal("0"),
        is_free_goods=free,
    )
    return invoice


def _cash_account(branch):
    return FinancialAccount.objects.create(
        code=f"CASH-{branch.code}",
        name=f"{branch.name} Cash",
        account_type=AccountType.CASH,
        branch=branch,
        allow_negative=False,
    )


def test_price_override_denied(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="9.0000")

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert exc.value.code == "PERMISSION_DENIED"
    assert "SALE_PRICE_OVERRIDE" in str(exc.value.detail)

    invoice.refresh_from_db()
    assert invoice.number is None
    assert StockBalance.objects.get().qty_on_hand == Decimal("10")


def test_price_override_allowed_with_permission(
    branch, customer, actor, medicine, batch, stock_in
):
    grant_role(actor, ["SALE_PRICE_OVERRIDE"])
    stock_in(batch, "10")
    # 11.00 differs from the tier price (12.00) but stays above cost (10.00).
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="11.0000")

    confirmed = confirm_sale(invoice=invoice, actor=actor)
    assert confirmed.number


def test_below_cost_denied(branch, customer, actor, medicine, batch, stock_in):
    grant_role(actor, ["SALE_PRICE_OVERRIDE"])
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="8.0000")

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert exc.value.code == "PERMISSION_DENIED"
    assert "SALE_BELOW_COST" in str(exc.value.detail)


def test_below_cost_allowed_with_permission(branch, customer, actor, medicine, batch, stock_in):
    grant_role(actor, ["SALE_PRICE_OVERRIDE", "SALE_BELOW_COST"])
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="8.0000")

    confirmed = confirm_sale(invoice=invoice, actor=actor)
    assert confirmed.grand_total == Decimal("16.00")


def test_free_goods_denied(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="0.0000", free=True)

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert "SALE_FREE_GOODS" in str(exc.value.detail)


def test_zero_value_denied_even_with_free_goods_permission(
    branch, customer, actor, medicine, batch, stock_in
):
    grant_role(actor, ["SALE_FREE_GOODS"])
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="0.0000", free=True)

    with pytest.raises(APIError) as exc:
        confirm_sale(invoice=invoice, actor=actor)
    assert "SALE_ZERO_VALUE" in str(exc.value.detail)


def test_free_goods_full_flow_with_both_permissions(
    branch, customer, actor, medicine, batch, stock_in
):
    grant_role(actor, ["SALE_FREE_GOODS", "SALE_ZERO_VALUE"])
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 2, unit_price="0.0000", free=True)

    confirmed = confirm_sale(invoice=invoice, actor=actor)
    assert confirmed.grand_total == Decimal("0.00")
    assert StockBalance.objects.get().qty_on_hand == Decimal("8")


def test_credit_override_requires_permission(branch, customer, actor):
    grant_role(actor, ["SALE_CONFIRM"], branch_scope=BranchScope.ALL)
    invoice = SalesInvoice.objects.create(
        branch=branch, customer=customer, business_date=timezone.localdate()
    )

    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(
        f"/api/v1/sales/{invoice.id}/confirm/",
        {"allow_credit_override": True, "credit_override_reason": "test"},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_cash_refund_requires_return_refund_permission(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 4)
    confirmed = confirm_sale(invoice=invoice, actor=actor)
    item = confirmed.items.get()

    with pytest.raises(APIError) as exc:
        create_sales_return(
            invoice=confirmed,
            reason_code="CUSTOMER_RETURN",
            refund_method="CASH",
            refund_account=_cash_account(branch),
            items_data=[{"invoice_item": item.id, "qty": Decimal("1"), "condition": "RESELLABLE"}],
            actor=actor,
        )
    assert exc.value.code == "PERMISSION_DENIED"
    assert "RETURN_REFUND" in str(exc.value.detail)


def test_cash_refund_allowed_with_permission(branch, customer, actor, medicine, batch, stock_in):
    grant_role(actor, ["RETURN_REFUND"])
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 4)
    confirmed = confirm_sale(invoice=invoice, actor=actor)
    item = confirmed.items.get()

    sales_return = create_sales_return(
        invoice=confirmed,
        reason_code="CUSTOMER_RETURN",
        refund_method="CASH",
        refund_account=_cash_account(branch),
        items_data=[{"invoice_item": item.id, "qty": Decimal("1"), "condition": "RESELLABLE"}],
        actor=actor,
    )
    assert sales_return.status == "DRAFT"


def test_cancel_invoice_with_returns_blocked(branch, customer, actor, medicine, batch, stock_in):
    stock_in(batch, "10")
    invoice = _draft_invoice(branch, customer, medicine, 4)
    confirmed = confirm_sale(invoice=invoice, actor=actor)
    item = confirmed.items.get()

    sales_return = create_sales_return(
        invoice=confirmed,
        reason_code="CUSTOMER_RETURN",
        refund_method="CUSTOMER_CREDIT",
        items_data=[{"invoice_item": item.id, "qty": Decimal("1"), "condition": "RESELLABLE"}],
        actor=actor,
    )
    confirm_sales_return(sales_return=sales_return, actor=actor)

    with pytest.raises(APIError) as exc:
        cancel_sale(invoice=confirmed, actor=actor, reason="too late")
    assert exc.value.code == "INVOICE_HAS_RETURNS"
    assert exc.value.status_code == 409

    confirmed.refresh_from_db()
    assert confirmed.lifecycle == "CONFIRMED"
    # 10 - 4 sold + 1 returned
    assert StockBalance.objects.get().qty_on_hand == Decimal("7")


def test_create_invoice_rejects_out_of_scope_branch(
    branch, second_branch, customer, actor, medicine
):
    grant_role(actor, ["SALE_CREATE"], branch_scope=BranchScope.ASSIGNED)
    UserBranch.objects.create(user=actor, branch=branch)
    actor._permission_cache = None

    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(
        "/api/v1/sales/",
        {
            "customer": str(customer.id),
            "branch": str(second_branch.id),
            "items": [{"medicine": str(medicine.id), "qty": "1", "unit_price": "12.0000"}],
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "BRANCH_SCOPE_EXCEEDED"
