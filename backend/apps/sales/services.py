"""Customer ledger + sales invoice services.

Sale confirmation is atomic: FEFO batch allocation, stock deduction, invoice
numbering, receivable posting and optional payment-at-entry all commit together.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.catalog.models import BatchStatus, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.inventory.models import EntryType
from apps.inventory.services import MovementLine, post_transactions
from apps.sales.models import (
    Customer,
    CustomerLedgerEntry,
    CustomerLedgerEntryType,
    SalesInvoice,
    SalesInvoiceItem,
    SalesInvoiceStatus,
)

TWO = Decimal("0.01")
FOUR = Decimal("0.0001")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def cost4(value) -> Decimal:
    return Decimal(value).quantize(FOUR, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- customer ledger


def post_customer_ledger_entry(
    *,
    customer: Customer,
    branch,
    entry_type: str,
    amount_delta: Decimal,
    due_date=None,
    source_type: str = "",
    source_id: UUID | None = None,
    source_number: str = "",
    business_date=None,
    actor=None,
    idempotency_key: str | None = None,
    reverses_entry: CustomerLedgerEntry | None = None,
    transaction_group_id: UUID | None = None,
) -> CustomerLedgerEntry:
    amount_delta = Decimal(amount_delta)
    if amount_delta == 0:
        raise ValueError("Customer ledger amount must not be zero.")

    if idempotency_key:
        existing = CustomerLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    entry = CustomerLedgerEntry.objects.create(
        customer=customer,
        branch=branch,
        entry_type=entry_type,
        amount_delta=amount_delta,
        due_date=due_date,
        source_type=source_type,
        source_id=source_id,
        source_number=source_number,
        transaction_group_id=transaction_group_id,
        reverses_entry=reverses_entry,
        idempotency_key=idempotency_key,
        business_date=business_date or timezone.localdate(),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    refresh_customer_balance(customer)
    return entry


def customer_balance_from_ledger(customer: Customer) -> Decimal:
    total = CustomerLedgerEntry.objects.filter(customer=customer).aggregate(
        total=Sum("amount_delta")
    )["total"]
    return total or Decimal("0")


def refresh_customer_balance(customer: Customer) -> Decimal:
    with transaction.atomic():
        locked = Customer.objects.select_for_update().get(id=customer.id)
        balance = customer_balance_from_ledger(locked)
        locked.balance_cache = balance
        locked.save(update_fields=["balance_cache", "updated_at"])
    return balance


# --------------------------------------------------------------------------- pricing / FEFO


def resolve_unit_price(medicine, customer: Customer) -> Decimal:
    tier = customer.price_tier
    if tier == "WHOLESALE" and medicine.wholesale_price:
        return medicine.wholesale_price
    if tier == "CUSTOM" and medicine.custom_price:
        return medicine.custom_price
    if tier == "RETAIL" and medicine.retail_price:
        return medicine.retail_price
    return medicine.selling_price


def fefo_allocate(branch, medicine, required_qty: Decimal) -> list[tuple[MedicineBatch, Decimal]]:
    """Pick saleable batches earliest-expiry-first and allocate the required quantity."""
    today = timezone.localdate()
    candidates = (
        MedicineBatch.objects.filter(branch=branch, medicine=medicine, status=BatchStatus.ACTIVE)
        .exclude(expiry_date__lt=today)
        .filter(qty_on_hand__gt=0)
        .order_by("expiry_date", "created_at")
    )
    remaining = Decimal(required_qty)
    allocations: list[tuple[MedicineBatch, Decimal]] = []
    for batch in candidates:
        if remaining <= 0:
            break
        take = min(remaining, batch.qty_on_hand)
        if take > 0:
            allocations.append((batch, take))
            remaining -= take
    if remaining > 0:
        available = Decimal(required_qty) - remaining
        raise APIError(
            "INSUFFICIENT_STOCK",
            (
                f"Only {available} saleable units available for {medicine.name}; "
                f"{required_qty} requested. Expired batches are never sellable."
            ),
            status_code=409,
        )
    return allocations


def fefo_candidates(branch, medicine) -> list[dict]:
    today = timezone.localdate()
    batches = (
        MedicineBatch.objects.filter(branch=branch, medicine=medicine, status=BatchStatus.ACTIVE)
        .exclude(expiry_date__lt=today)
        .filter(qty_on_hand__gt=0)
        .order_by("expiry_date", "created_at")
    )
    return [
        {
            "batch": batch.id,
            "batch_number": batch.batch_number,
            "expiry_date": batch.expiry_date,
            "qty_on_hand": batch.qty_on_hand,
            "unit_cost": batch.unit_cost,
            "days_to_expiry": (batch.expiry_date - today).days if batch.expiry_date else None,
        }
        for batch in batches
    ]


# --------------------------------------------------------------------------- confirmation


@transaction.atomic
def confirm_sale(
    *,
    invoice: SalesInvoice,
    actor,
    idempotency_key: str | None = None,
    payment: dict | None = None,
    allow_credit_override: bool = False,
    credit_override_reason: str = "",
) -> SalesInvoice:
    from apps.payments.services import record_customer_payment

    invoice = (
        SalesInvoice.objects.select_for_update()
        .select_related("customer", "branch")
        .get(id=invoice.id)
    )
    if invoice.lifecycle == SalesInvoiceStatus.CONFIRMED:
        return invoice
    if invoice.lifecycle != SalesInvoiceStatus.DRAFT:
        raise APIError("INVALID_STATUS_TRANSITION", "Only draft invoices can be confirmed.")

    if idempotency_key:
        existing = (
            SalesInvoice.objects.filter(idempotency_key=idempotency_key).exclude(id=invoice.id).first()
        )
        if existing is not None:
            return existing

    customer = Customer.objects.select_for_update().get(id=invoice.customer_id)
    if customer.credit_hold:
        raise APIError(
            "CUSTOMER_ON_HOLD",
            "Customer is on credit hold; new sales are blocked.",
            status_code=409,
        )

    block_days = getattr(settings, "CUSTOMER_OVERDUE_BLOCK_DAYS", 30)
    overdue_cutoff = invoice.business_date - timedelta(days=block_days)
    has_past_due = SalesInvoice.objects.filter(
        customer=customer,
        lifecycle=SalesInvoiceStatus.CONFIRMED,
        due_date__lt=overdue_cutoff,
        paid_total__lt=F("grand_total"),
    ).exists()
    if has_past_due:
        if not allow_credit_override:
            raise APIError(
                "CUSTOMER_PAST_DUE",
                (
                    f"Customer has invoices overdue by more than {block_days} days. "
                    "Collect dues or use a credit override."
                ),
                status_code=409,
            )
        invoice.credit_override = True
        invoice.credit_override_reason = credit_override_reason or "past-due override"
    if customer.credit_limit > 0:
        projected = customer.balance_cache + invoice.grand_total
        if projected > customer.credit_limit:
            if not allow_credit_override:
                raise APIError(
                    "CREDIT_LIMIT_EXCEEDED",
                    (
                        f"Credit limit exceeded: balance {customer.balance_cache} + invoice "
                        f"{invoice.grand_total} > limit {customer.credit_limit}."
                    ),
                    status_code=409,
                )
            invoice.credit_override = True
            invoice.credit_override_reason = credit_override_reason

    draft_items = list(invoice.items.select_related("medicine").order_by("line_no"))
    if not draft_items:
        raise APIError("EMPTY_INVOICE", "An invoice must have at least one line.")

    invoice.number = allocate_number(
        branch=invoice.branch,
        doc_type=DocumentType.SALES_INVOICE,
        business_date=invoice.business_date,
    )

    movement_lines: list[MovementLine] = []
    expanded: list[tuple[SalesInvoiceItem, MedicineBatch, Decimal]] = []

    for item in draft_items:
        allocations = fefo_allocate(invoice.branch, item.medicine, item.qty)
        for batch, take in allocations:
            movement_lines.append(
                MovementLine(
                    medicine=item.medicine,
                    batch=batch,
                    qty_delta=-take,
                    unit_cost=batch.unit_cost,
                )
            )
            expanded.append((item, batch, take))

    post_transactions(
        branch=invoice.branch,
        lines=movement_lines,
        entry_type=EntryType.SALE,
        source_type="SALES_INVOICE",
        source_id=invoice.id,
        source_number=invoice.number,
        business_date=invoice.business_date,
        actor=actor,
    )

    # Persist one final line per batch, splitting discount/VAT proportionally.
    snapshots = {
        item.id: {
            "medicine": item.medicine,
            "qty": item.qty,
            "unit_price": item.unit_price,
            "line_discount": item.line_discount,
            "vat_rate": item.vat_rate,
            "vat_amount": item.vat_amount,
            "is_free_goods": item.is_free_goods,
        }
        for item in draft_items
    }
    invoice.items.all().delete()

    line_no = 1
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    vat_total = Decimal("0")
    for draft_item, batch, take in expanded:
        snapshot = snapshots[draft_item.id]
        share = take / snapshot["qty"]
        gross = money(take * snapshot["unit_price"])
        line_discount = money(snapshot["line_discount"] * share)
        vat_amount = money(snapshot["vat_amount"] * share)
        line_net = money(gross - line_discount)

        SalesInvoiceItem.objects.create(
            invoice=invoice,
            line_no=line_no,
            medicine=snapshot["medicine"],
            batch=batch,
            batch_number=batch.batch_number,
            qty=take,
            unit_price=cost4(snapshot["unit_price"]),
            line_discount=line_discount,
            vat_rate=snapshot["vat_rate"],
            vat_amount=vat_amount,
            line_net=line_net,
            unit_cost=batch.unit_cost,
            is_free_goods=snapshot["is_free_goods"],
        )
        subtotal += gross
        discount_total += line_discount
        vat_total += vat_amount
        line_no += 1

    net_total = money(subtotal - discount_total + vat_total)
    grand_total = net_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    invoice.subtotal = money(subtotal)
    invoice.discount_total = money(discount_total)
    invoice.vat_total = money(vat_total)
    invoice.round_off = money(grand_total - net_total)
    invoice.grand_total = money(grand_total)
    invoice.due_date = invoice.business_date + timedelta(days=customer.credit_days)
    invoice.lifecycle = SalesInvoiceStatus.CONFIRMED
    invoice.confirmed_at = timezone.now()
    invoice.confirmed_by = actor if getattr(actor, "is_authenticated", False) else None
    invoice.idempotency_key = idempotency_key or invoice.idempotency_key
    invoice.save()

    post_customer_ledger_entry(
        customer=customer,
        branch=invoice.branch,
        entry_type=CustomerLedgerEntryType.INVOICE,
        amount_delta=invoice.grand_total,
        due_date=invoice.due_date,
        source_type="SALES_INVOICE",
        source_id=invoice.id,
        source_number=invoice.number,
        business_date=invoice.business_date,
        actor=actor,
    )

    if payment and Decimal(payment["amount"]) > 0:
        record_customer_payment(
            customer=customer,
            branch=invoice.branch,
            amount=Decimal(payment["amount"]),
            method=payment["method"],
            account=payment["account"],
            business_date=invoice.business_date,
            reference=payment.get("reference", ""),
            allocations=[
                {"invoice": invoice, "amount": min(Decimal(payment["amount"]), invoice.outstanding)}
            ],
            actor=actor,
            idempotency_key=f"confirm-receipt:{invoice.id}",
        )

    invoice.refresh_from_db()
    return invoice


@transaction.atomic
def cancel_sale(*, invoice: SalesInvoice, actor, reason: str = "") -> SalesInvoice:
    invoice = (
        SalesInvoice.objects.select_for_update()
        .select_related("customer", "branch")
        .get(id=invoice.id)
    )
    if invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only confirmed invoices can be cancelled.")
    if invoice.paid_total > 0:
        raise APIError(
            "INVOICE_HAS_PAYMENTS",
            "Reverse receipts before cancelling; or process a sales return.",
            status_code=409,
        )

    items = list(invoice.items.select_related("medicine", "batch"))
    restock_lines = [
        MovementLine(
            medicine=item.medicine,
            batch=item.batch,
            qty_delta=item.qty,
            unit_cost=item.unit_cost,
        )
        for item in items
        if item.batch is not None
    ]
    if restock_lines:
        post_transactions(
            branch=invoice.branch,
            lines=restock_lines,
            entry_type=EntryType.REVERSAL,
            source_type="SALES_CANCEL",
            source_id=invoice.id,
            source_number=invoice.number or "",
            business_date=timezone.localdate(),
            actor=actor,
        )

    post_customer_ledger_entry(
        customer=invoice.customer,
        branch=invoice.branch,
        entry_type=CustomerLedgerEntryType.ADJUSTMENT,
        amount_delta=-invoice.grand_total,
        source_type="SALES_CANCEL",
        source_id=invoice.id,
        source_number=invoice.number or "",
        business_date=timezone.localdate(),
        actor=actor,
    )

    invoice.lifecycle = SalesInvoiceStatus.CANCELLED
    invoice.cancel_reason = reason
    invoice.save(update_fields=["lifecycle", "cancel_reason", "updated_at"])
    return invoice
