from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.sales.delivery_models import ChallanStatus, DeliveryChallan, DeliveryChallanItem
from apps.sales.models import FulfillmentStatus, SalesInvoice, SalesInvoiceStatus


@transaction.atomic
def create_delivery_challan(
    *,
    branch,
    customer,
    invoice: SalesInvoice | None = None,
    business_date,
    delivery_person: str = "",
    delivery_phone: str = "",
    vehicle_no: str = "",
    notes: str = "",
    items: list[dict],
    actor=None,
    idempotency_key: str | None = None,
) -> DeliveryChallan:
    if idempotency_key:
        existing = DeliveryChallan.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if not items:
        raise APIError("EMPTY_CHALLAN", "A delivery challan must have at least one line item.")

    number = allocate_number(
        branch=branch,
        doc_type=DocumentType.DELIVERY_CHALLAN,
        business_date=business_date,
    )

    challan = DeliveryChallan.objects.create(
        number=number,
        branch=branch,
        customer=customer,
        invoice=invoice,
        business_date=business_date,
        status=ChallanStatus.PREPARED,
        delivery_person=delivery_person,
        delivery_phone=delivery_phone,
        vehicle_no=vehicle_no,
        notes=notes,
        idempotency_key=idempotency_key,
    )

    for idx, item in enumerate(items, start=1):
        DeliveryChallanItem.objects.create(
            challan=challan,
            line_no=idx,
            medicine=item["medicine"],
            batch=item.get("batch"),
            batch_number=item.get("batch_number", "DEFAULT"),
            qty=item["qty"],
            notes=item.get("notes", ""),
        )

    return challan


@transaction.atomic
def create_challan_from_invoice(
    *,
    invoice: SalesInvoice,
    delivery_person: str = "",
    delivery_phone: str = "",
    vehicle_no: str = "",
    notes: str = "",
    actor=None,
    idempotency_key: str | None = None,
) -> DeliveryChallan:
    """Create a delivery challan from a confirmed sales invoice."""
    invoice = SalesInvoice.objects.select_related("customer", "branch").get(id=invoice.id)
    if invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
        raise APIError("INVOICE_NOT_CONFIRMED", "Delivery challans can only be created from confirmed invoices.")

    invoice_items = list(invoice.items.select_related("medicine", "batch").order_by("line_no"))
    if not invoice_items:
        raise APIError("EMPTY_INVOICE", "Invoice has no line items to dispatch.")

    items = []
    for item in invoice_items:
        items.append({
            "medicine": item.medicine,
            "batch": item.batch,
            "batch_number": item.batch.batch_number if item.batch else (item.batch_number or "DEFAULT"),
            "qty": item.qty,
            "notes": f"Invoice {invoice.number or invoice.id}",
        })

    return create_delivery_challan(
        branch=invoice.branch,
        customer=invoice.customer,
        invoice=invoice,
        business_date=timezone.localdate(),
        delivery_person=delivery_person,
        delivery_phone=delivery_phone,
        vehicle_no=vehicle_no,
        notes=notes,
        items=items,
        actor=actor,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def dispatch_delivery_challan(*, challan: DeliveryChallan, actor) -> DeliveryChallan:
    challan = DeliveryChallan.objects.select_for_update().get(id=challan.id)
    if challan.status != ChallanStatus.PREPARED:
        raise APIError("INVALID_STATUS", f"Only prepared challans can be dispatched (current: {challan.status}).")

    challan.status = ChallanStatus.DISPATCHED
    challan.dispatched_at = timezone.now()
    challan.dispatched_by = actor
    challan.save()
    return challan


@transaction.atomic
def complete_delivery_challan(
    *,
    challan: DeliveryChallan,
    actor,
    recipient_name: str = "",
    recipient_phone: str = "",
    notes: str = "",
) -> DeliveryChallan:
    challan = (
        DeliveryChallan.objects.select_for_update(of=("self",))
        .select_related("invoice")
        .get(id=challan.id)
    )
    if challan.status not in (ChallanStatus.PREPARED, ChallanStatus.DISPATCHED):
        raise APIError("INVALID_STATUS", f"Cannot mark challan as delivered from status {challan.status}.")

    now = timezone.now()
    challan.status = ChallanStatus.DELIVERED
    challan.delivered_at = now
    challan.delivered_by = actor
    if recipient_name:
        challan.recipient_name = recipient_name
    if recipient_phone:
        challan.recipient_phone = recipient_phone
    if notes:
        challan.notes = f"{challan.notes}\n{notes}".strip()
    challan.save()

    if challan.invoice:
        invoice = SalesInvoice.objects.select_for_update().get(id=challan.invoice_id)
        invoice.fulfillment_status = FulfillmentStatus.DELIVERED
        invoice.delivered_at = now
        invoice.delivered_by = actor
        invoice.save()

    return challan


@transaction.atomic
def mark_undelivered_challan(*, challan: DeliveryChallan, actor, reason: str = "") -> DeliveryChallan:
    challan = DeliveryChallan.objects.select_for_update().get(id=challan.id)
    if challan.status != ChallanStatus.DISPATCHED:
        raise APIError("INVALID_STATUS", f"Only dispatched challans can be marked undelivered (current: {challan.status}).")

    challan.status = ChallanStatus.UNDELIVERED
    challan.cancel_reason = reason
    challan.save()
    return challan


@transaction.atomic
def cancel_delivery_challan(*, challan: DeliveryChallan, actor, reason: str = "") -> DeliveryChallan:
    challan = DeliveryChallan.objects.select_for_update().get(id=challan.id)
    if challan.status == ChallanStatus.DELIVERED:
        raise APIError("CANNOT_CANCEL", "Delivered challans cannot be cancelled.")

    challan.status = ChallanStatus.CANCELLED
    challan.cancel_reason = reason
    challan.save()
    return challan
