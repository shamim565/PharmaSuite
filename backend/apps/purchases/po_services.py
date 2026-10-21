from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.common.settings_service import get_setting_bool
from apps.purchases.models import Purchase, PurchaseItem, PurchaseStatus
from apps.purchases.po_models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.purchases.services import money


def compute_po_line_totals(item: dict) -> dict:
    qty = Decimal(str(item["qty_ordered"]))
    unit_cost = Decimal(str(item.get("unit_cost") or 0))
    discount = money(item.get("line_discount") or 0)
    vat_rate = Decimal(str(item.get("vat_rate") if item.get("vat_rate") is not None else 15))
    if not get_setting_bool("PURCHASE_VAT_ENABLED", default=False):
        vat_rate = Decimal("0")

    gross = money(qty * unit_cost)
    taxable = money(gross - discount)
    vat_amount = money(taxable * vat_rate / Decimal("100"))
    line_net = money(taxable + vat_amount)

    return {
        "qty_ordered": qty,
        "unit_cost": unit_cost,
        "line_discount": discount,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "line_net": line_net,
    }


def compute_po_totals(items: list[dict]) -> dict:
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    vat_total = Decimal("0")
    for item in items:
        subtotal += money(Decimal(str(item["qty_ordered"])) * Decimal(str(item.get("unit_cost") or 0)))
        discount_total += money(item.get("line_discount") or 0)
        vat_total += money(item.get("vat_amount") or 0)
    grand_total = money(subtotal - discount_total + vat_total)
    return {
        "subtotal": subtotal,
        "discount_total": discount_total,
        "vat_total": vat_total,
        "grand_total": grand_total,
    }


@transaction.atomic
def create_purchase_order(
    *,
    branch,
    supplier,
    business_date,
    items: list[dict],
    notes: str = "",
    expected_delivery_date=None,
    actor=None,
    idempotency_key: str | None = None,
) -> PurchaseOrder:
    if idempotency_key:
        existing = PurchaseOrder.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if not items:
        raise APIError("EMPTY_PURCHASE_ORDER", "A purchase order must contain at least one item.")

    computed_items = []
    for item in items:
        calc = compute_po_line_totals(item)
        computed_items.append({**item, **calc})

    totals = compute_po_totals(computed_items)

    po = PurchaseOrder.objects.create(
        branch=branch,
        supplier=supplier,
        business_date=business_date,
        expected_delivery_date=expected_delivery_date,
        status=PurchaseOrderStatus.DRAFT,
        notes=notes,
        subtotal=totals["subtotal"],
        discount_total=totals["discount_total"],
        vat_total=totals["vat_total"],
        grand_total=totals["grand_total"],
        idempotency_key=idempotency_key,
    )

    for idx, c_item in enumerate(computed_items, start=1):
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            line_no=idx,
            medicine=c_item["medicine"],
            qty_ordered=c_item["qty_ordered"],
            unit_cost=c_item["unit_cost"],
            line_discount=c_item["line_discount"],
            vat_rate=c_item["vat_rate"],
            vat_amount=c_item["vat_amount"],
            line_net=c_item["line_net"],
            notes=c_item.get("notes", ""),
        )

    return po


@transaction.atomic
def submit_purchase_order(*, purchase_order: PurchaseOrder, actor) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(id=purchase_order.id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise APIError("INVALID_STATUS", f"Only draft purchase orders can be submitted (current: {po.status}).")

    if not po.items.exists():
        raise APIError("EMPTY_PURCHASE_ORDER", "Cannot submit an empty purchase order.")

    po.status = PurchaseOrderStatus.SUBMITTED
    po.submitted_at = timezone.now()
    po.submitted_by = actor
    po.save()
    return po


@transaction.atomic
def approve_purchase_order(*, purchase_order: PurchaseOrder, actor) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(id=purchase_order.id)
    if po.status not in (PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.SUBMITTED):
        raise APIError("INVALID_STATUS", f"Purchase order cannot be approved from status {po.status}.")

    if not po.items.exists():
        raise APIError("EMPTY_PURCHASE_ORDER", "Cannot approve an empty purchase order.")

    if not po.number:
        po.number = allocate_number(
            branch=po.branch,
            doc_type=DocumentType.PURCHASE_ORDER,
            business_date=po.business_date,
        )

    po.status = PurchaseOrderStatus.APPROVED
    po.approved_at = timezone.now()
    po.approved_by = actor
    po.save()
    return po


@transaction.atomic
def cancel_purchase_order(*, purchase_order: PurchaseOrder, actor, reason: str = "") -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(id=purchase_order.id)
    if po.status in (PurchaseOrderStatus.FULLY_RECEIVED, PurchaseOrderStatus.CANCELLED):
        raise APIError("CANNOT_CANCEL", f"Cannot cancel purchase order with status {po.status}.")

    po.status = PurchaseOrderStatus.CANCELLED
    po.cancel_reason = reason
    po.cancelled_by = actor
    po.save()
    return po


@transaction.atomic
def convert_po_to_purchase(
    *,
    purchase_order: PurchaseOrder,
    actor,
    supplier_invoice_number: str,
    supplier_invoice_date,
    idempotency_key: str | None = None,
) -> Purchase:
    """Create a draft Purchase (GRN) from an approved Purchase Order."""
    po = PurchaseOrder.objects.select_for_update().get(id=purchase_order.id)
    if po.status not in (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.PARTIALLY_RECEIVED):
        raise APIError(
            "PO_NOT_APPROVED",
            f"Only approved or partially received purchase orders can be converted to purchases (current: {po.status}).",
        )

    items = list(po.items.select_related("medicine").order_by("line_no"))
    if not items:
        raise APIError("EMPTY_PO", "Purchase order has no items.")

    today = timezone.localdate()
    purchase = Purchase.objects.create(
        branch=po.branch,
        supplier=po.supplier,
        supplier_invoice_number=supplier_invoice_number,
        supplier_invoice_date=supplier_invoice_date or today,
        business_date=today,
        lifecycle=PurchaseStatus.DRAFT,
        subtotal=po.subtotal,
        discount_total=po.discount_total,
        vat_total=po.vat_total,
        grand_total=po.grand_total,
        notes=f"Converted from PO {po.number or po.id}",
        idempotency_key=idempotency_key,
    )

    for item in items:
        pending_qty = item.qty_pending
        if pending_qty <= 0:
            continue
        PurchaseItem.objects.create(
            purchase=purchase,
            line_no=item.line_no,
            medicine=item.medicine,
            batch_number=f"PO-{item.line_no}",
            conversion_factor=Decimal("1"),
            qty_entered=pending_qty,
            qty_base=pending_qty,
            unit_cost=item.unit_cost,
            line_discount=item.line_discount,
            vat_rate=item.vat_rate,
            vat_amount=item.vat_amount,
            line_net=item.line_net,
            base_unit_cost=item.unit_cost,
            effective_unit_cost=item.unit_cost,
        )
        item.qty_received += pending_qty
        item.save()

    po.fulfilled_by = purchase
    po.status = PurchaseOrderStatus.FULLY_RECEIVED
    po.save()

    return purchase
