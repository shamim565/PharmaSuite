"""Returns without an original invoice (SRET_NO_INVOICE)."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import AccountType, FinancialAccount, FinancialEntryType
from apps.accounting.services import post_account_transaction
from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.common.exceptions import APIError
from apps.inventory.models import StockBalance
from apps.sales.models import CustomerLedgerEntry, SalesReturn
from apps.sales.services import confirm_sales_return, create_direct_return

pytestmark = pytest.mark.django_db


def _cash_account(branch, actor):
    account = FinancialAccount.objects.create(
        code=f"CASH-{branch.code}",
        name=f"{branch.name} Cash",
        account_type=AccountType.CASH,
        branch=branch,
        allow_negative=False,
    )
    post_account_transaction(
        account=account,
        entry_type=FinancialEntryType.OPENING,
        amount_delta=Decimal("100.00"),
        business_date=timezone.localdate(),
        actor=actor,
    )
    return account


def _direct_return(branch, customer, medicine, batch, qty="3", condition="RESELLABLE", **extra):
    return create_direct_return(
        customer=customer,
        branch=branch,
        reason_code="CUSTOMER_RETURN",
        refund_method=extra.pop("refund_method", "CUSTOMER_CREDIT"),
        refund_account=extra.pop("refund_account", None),
        items_data=[
            {
                "medicine": medicine,
                "batch": batch,
                "qty": Decimal(qty),
                "condition": condition,
            }
        ],
        **extra,
    )


def test_direct_return_requires_permission(branch, customer, medicine, batch, actor):
    with pytest.raises(APIError) as exc:
        _direct_return(branch, customer, medicine, batch, actor=actor)
    assert exc.value.code == "PERMISSION_DENIED"
    assert "SRET_NO_INVOICE" in str(exc.value.detail)


def test_direct_return_restocks_and_credits_customer(
    branch, customer, medicine, batch, stock_in, actor
):
    grant_role(actor, ["SRET_NO_INVOICE"])
    stock_in(batch, "10")

    sales_return = _direct_return(branch, customer, medicine, batch, actor=actor)
    assert sales_return.invoice_id is None
    assert sales_return.status == "DRAFT"

    confirmed = confirm_sales_return(sales_return=sales_return, actor=actor)

    assert confirmed.status == "CONFIRMED"
    assert confirmed.number and confirmed.number.startswith("CRN-")
    assert confirmed.grand_total == Decimal("36.00")  # 3 × tier price 12.00
    # No invoice deduction exists, so the returned goods add back to stock.
    assert StockBalance.objects.get().qty_on_hand == Decimal("13")

    ledger = CustomerLedgerEntry.objects.get(entry_type="SALES_RETURN")
    assert ledger.amount_delta == Decimal("-36.00")

    customer.refresh_from_db()
    assert customer.balance_cache == Decimal("-36.00")


def test_direct_return_damaged_goes_to_quarantine(
    branch, customer, medicine, batch, stock_in, actor
):
    grant_role(actor, ["SRET_NO_INVOICE"])
    stock_in(batch, "10")

    sales_return = _direct_return(
        branch, customer, medicine, batch, condition="DAMAGED", actor=actor
    )
    confirm_sales_return(sales_return=sales_return, actor=actor)

    balance = StockBalance.objects.get()
    assert balance.qty_on_hand == Decimal("10")
    assert balance.qty_quarantine == Decimal("3")


def test_direct_return_batch_must_belong_to_branch(
    branch, second_branch, customer, medicine, make_batch, actor
):
    grant_role(actor, ["SRET_NO_INVOICE"])
    foreign_batch = make_batch(batch_number="FOREIGN")
    foreign_batch.branch = second_branch
    foreign_batch.save(update_fields=["branch", "updated_at"])

    with pytest.raises(APIError) as exc:
        _direct_return(branch, customer, medicine, foreign_batch, actor=actor)
    assert exc.value.code == "INVALID_BATCH"
    assert SalesReturn.objects.count() == 0


def test_direct_return_cash_refund_requires_return_refund(
    branch, customer, medicine, batch, stock_in, actor
):
    grant_role(actor, ["SRET_NO_INVOICE"])
    account = _cash_account(branch, actor)
    stock_in(batch, "10")

    with pytest.raises(APIError) as exc:
        _direct_return(
            branch,
            customer,
            medicine,
            batch,
            actor=actor,
            refund_method="CASH",
            refund_account=account,
        )
    assert "RETURN_REFUND" in str(exc.value.detail)

    grant_role(actor, ["RETURN_REFUND"])
    sales_return = _direct_return(
        branch,
        customer,
        medicine,
        batch,
        actor=actor,
        refund_method="CASH",
        refund_account=account,
    )
    confirmed = confirm_sales_return(sales_return=sales_return, actor=actor)
    assert confirmed.status == "CONFIRMED"


def test_direct_return_api_endpoint(branch, customer, medicine, batch, stock_in, actor):
    grant_role(actor, ["SRET_NO_INVOICE", "SRET_CONFIRM"], branch_scope=BranchScope.ALL)
    stock_in(batch, "10")

    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(
        "/api/v1/sales-returns/direct/",
        {
            "customer": str(customer.id),
            "branch": str(branch.id),
            "reason_code": "CUSTOMER_RETURN",
            "refund_method": "CUSTOMER_CREDIT",
            "items": [
                {
                    "medicine": str(medicine.id),
                    "batch": str(batch.id),
                    "qty": "2",
                    "condition": "RESELLABLE",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["invoice"] is None
    assert body["invoice_number"] is None

    confirmed = client.post(f"/api/v1/sales-returns/{body['id']}/confirm/", {}, format="json")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"
    assert StockBalance.objects.get().qty_on_hand == Decimal("12")
