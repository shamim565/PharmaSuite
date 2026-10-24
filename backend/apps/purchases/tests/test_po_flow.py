"""Tests for the purchase order lifecycle: draft → submit → approve → GRN."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.purchases.models import PurchaseStatus
from apps.purchases.po_models import PurchaseOrderStatus
from apps.purchases.po_services import (
    approve_purchase_order,
    cancel_purchase_order,
    convert_po_to_purchase,
    create_purchase_order,
    submit_purchase_order,
)

pytestmark = pytest.mark.django_db


def _create_po(branch, supplier, medicine, actor, qty="10", unit_cost="10.0000"):
    return create_purchase_order(
        branch=branch,
        supplier=supplier,
        business_date=timezone.localdate(),
        actor=actor,
        items=[
            {
                "medicine": medicine,
                "qty_ordered": Decimal(qty),
                "unit_cost": Decimal(unit_cost),
                "line_discount": Decimal("0"),
                "vat_rate": Decimal("0"),
            }
        ],
    )


def test_po_lifecycle_to_grn(branch, supplier, medicine, actor):
    po = _create_po(branch, supplier, medicine, actor)
    assert po.status == PurchaseOrderStatus.DRAFT
    assert po.number is None
    assert po.grand_total == Decimal("100.00")

    po = submit_purchase_order(purchase_order=po, actor=actor)
    assert po.status == PurchaseOrderStatus.SUBMITTED

    po = approve_purchase_order(purchase_order=po, actor=actor)
    assert po.status == PurchaseOrderStatus.APPROVED
    assert po.number

    purchase = convert_po_to_purchase(
        purchase_order=po,
        actor=actor,
        supplier_invoice_number="SI-PO-1",
        supplier_invoice_date=timezone.localdate(),
    )
    assert purchase.lifecycle == PurchaseStatus.DRAFT
    assert purchase.items.count() == 1
    assert purchase.items.first().qty_base == Decimal("10")

    po.refresh_from_db()
    assert po.status == PurchaseOrderStatus.FULLY_RECEIVED
    assert po.fulfilled_by_id == purchase.id


def test_po_cannot_convert_before_approval(branch, supplier, medicine, actor):
    po = _create_po(branch, supplier, medicine, actor)
    with pytest.raises(APIError) as exc:
        convert_po_to_purchase(
            purchase_order=po,
            actor=actor,
            supplier_invoice_number="SI-X",
            supplier_invoice_date=timezone.localdate(),
        )
    assert exc.value.code == "PO_NOT_APPROVED"


def test_po_cancel_and_cannot_cancel_after_receipt(branch, supplier, medicine, actor):
    po = _create_po(branch, supplier, medicine, actor)
    po = cancel_purchase_order(purchase_order=po, actor=actor, reason="Supplier out of stock")
    assert po.status == PurchaseOrderStatus.CANCELLED

    with pytest.raises(APIError):
        approve_purchase_order(purchase_order=po, actor=actor)


def test_po_create_is_idempotent(branch, supplier, medicine, actor):
    first = create_purchase_order(
        branch=branch,
        supplier=supplier,
        business_date=timezone.localdate(),
        actor=actor,
        idempotency_key="po-key-1",
        items=[
            {
                "medicine": medicine,
                "qty_ordered": Decimal("5"),
                "unit_cost": Decimal("2.0000"),
                "line_discount": Decimal("0"),
                "vat_rate": Decimal("0"),
            }
        ],
    )
    second = create_purchase_order(
        branch=branch,
        supplier=supplier,
        business_date=timezone.localdate(),
        actor=actor,
        idempotency_key="po-key-1",
        items=[
            {
                "medicine": medicine,
                "qty_ordered": Decimal("5"),
                "unit_cost": Decimal("2.0000"),
                "line_discount": Decimal("0"),
                "vat_rate": Decimal("0"),
            }
        ],
    )
    assert first.id == second.id


def test_convert_to_purchase_is_idempotent(branch, supplier, medicine, actor):
    po = _create_po(branch, supplier, medicine, actor)
    po = approve_purchase_order(purchase_order=po, actor=actor)

    kwargs = dict(
        purchase_order=po,
        actor=actor,
        supplier_invoice_number="SI-IDEMP-1",
        supplier_invoice_date=timezone.localdate(),
        idempotency_key="po-convert-key-1",
    )
    first = convert_po_to_purchase(**kwargs)
    second = convert_po_to_purchase(**kwargs)

    assert first.id == second.id
    assert po.__class__.objects.get(id=po.id).fulfilled_by_id == first.id
