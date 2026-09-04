"""Purchase record PDF rendering endpoint."""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import confirm_purchase

pytestmark = pytest.mark.django_db


def _confirmed_purchase(branch, supplier, medicine, actor):
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
        batch_number="PB-1",
        expiry_date=timezone.localdate(),
        qty_entered=Decimal("5"),
        qty_base=Decimal("5"),
        unit_cost=Decimal("10.0000"),
        base_unit_cost=Decimal("10.0000"),
        effective_unit_cost=Decimal("10.0000"),
    )
    purchase.subtotal = Decimal("50.00")
    purchase.grand_total = Decimal("50.00")
    purchase.save(update_fields=["subtotal", "grand_total", "updated_at"])
    return confirm_purchase(purchase=purchase, actor=actor)


def test_purchase_pdf_download(branch, supplier, medicine, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    purchase = _confirmed_purchase(branch, supplier, medicine, actor)

    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/purchases/{purchase.id}/print/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response["Content-Disposition"]


def test_purchase_pdf_requires_purchase_view(branch, supplier, medicine, actor):
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    purchase = _confirmed_purchase(branch, supplier, medicine, actor)

    grant_role(actor, ["USER_VIEW"], branch_scope=BranchScope.ALL)
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(f"/api/v1/purchases/{purchase.id}/print/")

    assert response.status_code == 403
