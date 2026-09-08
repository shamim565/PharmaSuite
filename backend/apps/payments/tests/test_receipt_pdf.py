"""Customer payment receipt PDF rendering endpoint."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounting.models import AccountType, FinancialAccount, FinancialEntryType
from apps.accounting.services import post_account_transaction
from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.payments.models import PaymentMethod
from apps.payments.services import record_customer_payment

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


def test_receipt_pdf_download(branch, customer, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    account = _cash_account(branch, actor)
    payment = record_customer_payment(
        customer=customer,
        branch=branch,
        amount=Decimal("25.00"),
        method=PaymentMethod.CASH,
        account=account,
        actor=actor,
    )

    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/payments/{payment.id}/print/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response["Content-Disposition"]


def test_receipt_pdf_requires_payment_view(branch, customer, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    account = _cash_account(branch, actor)
    payment = record_customer_payment(
        customer=customer,
        branch=branch,
        amount=Decimal("25.00"),
        method=PaymentMethod.CASH,
        account=account,
        actor=actor,
    )

    grant_role(actor, ["USER_VIEW"], branch_scope=BranchScope.ALL)
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/payments/{payment.id}/print/")

    assert response.status_code == 403


def test_supplier_payments_filterable_by_purchase(branch, supplier, medicine, actor):
    """The purchase field filter powers payment-history on the purchase detail page."""
    from apps.accounting.models import AccountType, FinancialAccount, FinancialEntryType
    from apps.accounting.services import post_account_transaction
    from apps.purchases.models import Purchase, PurchaseItem
    from apps.purchases.services import confirm_purchase, record_supplier_payment
    from uuid import uuid4

    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    account = _cash_account(branch, actor)

    purchase = Purchase.objects.create(
        branch=branch,
        supplier=supplier,
        supplier_invoice_number=f"SI-{uuid4().hex[:8]}",
        supplier_invoice_date=timezone.localdate(),
        business_date=timezone.localdate(),
    )
    PurchaseItem.objects.create(
        purchase=purchase,
        line_no=1,
        medicine=medicine,
        batch_number="PB-2",
        expiry_date=timezone.localdate(),
        qty_entered=Decimal("6"),
        qty_base=Decimal("6"),
        unit_cost=Decimal("10.0000"),
        base_unit_cost=Decimal("10.0000"),
        effective_unit_cost=Decimal("10.0000"),
    )
    purchase.subtotal = Decimal("60.00")
    purchase.grand_total = Decimal("60.00")
    purchase.save(update_fields=["subtotal", "grand_total", "updated_at"])
    purchase = confirm_purchase(purchase=purchase, actor=actor)

    record_supplier_payment(
        supplier=supplier,
        branch=branch,
        amount=Decimal("60.00"),
        method=PaymentMethod.CASH,
        account=account,
        allocations=[{"purchase": purchase, "amount": Decimal("60.00")}],
        actor=actor,
    )

    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/supplier-payments/?purchase={purchase.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["allocations"][0]["purchase"] == str(purchase.id)
