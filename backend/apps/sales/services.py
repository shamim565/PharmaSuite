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

from apps.accounting.models import FinancialEntryType
from apps.accounting.services import post_account_transaction
from apps.catalog.models import BatchStatus, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.inventory.models import EntryType, StockBalance, StockPool
from apps.inventory.services import MovementLine, post_transactions
from apps.sales.models import (
    Customer,
    CustomerLedgerEntry,
    CustomerLedgerEntryType,
    RefundMethod,
    ReturnCondition,
    SalesInvoice,
    SalesInvoiceItem,
    SalesInvoiceStatus,
    SalesPaymentStatus,
    SalesReturn,
    SalesReturnDocStatus,
    SalesReturnItem,
    SalesReturnStatus,
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

    from apps.common.periods import ensure_period_open

    ensure_period_open(business_date, actor)

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
    """Pick saleable batches earliest-expiry-first and allocate the required quantity.

    Availability is read from the authoritative ``StockBalance`` cache (not the
    display-only ``MedicineBatch.qty_on_hand``), so FEFO can never allocate
    against a drifted batch cache.
    """
    today = timezone.localdate()
    candidates = (
        StockBalance.objects.filter(
            branch=branch,
            medicine=medicine,
            qty_on_hand__gt=0,
            batch__status=BatchStatus.ACTIVE,
        )
        .exclude(batch__expiry_date__lt=today)
        .select_related("batch")
        .order_by("batch__expiry_date", "batch__created_at")
    )
    remaining = Decimal(required_qty)
    allocations: list[tuple[MedicineBatch, Decimal]] = []
    for balance in candidates:
        if remaining <= 0:
            break
        take = min(remaining, balance.qty_on_hand)
        if take > 0:
            allocations.append((balance.batch, take))
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
    balances = (
        StockBalance.objects.filter(
            branch=branch,
            medicine=medicine,
            qty_on_hand__gt=0,
            batch__status=BatchStatus.ACTIVE,
        )
        .exclude(batch__expiry_date__lt=today)
        .select_related("batch")
        .order_by("batch__expiry_date", "batch__created_at")
    )
    return [
        {
            "batch": balance.batch.id,
            "batch_number": balance.batch.batch_number,
            "expiry_date": balance.batch.expiry_date,
            "qty_on_hand": balance.qty_on_hand,
            "unit_cost": balance.batch.unit_cost,
            "days_to_expiry": (balance.batch.expiry_date - today).days
            if balance.batch.expiry_date
            else None,
        }
        for balance in balances
    ]


# --------------------------------------------------------------------------- confirmation


def _require_sale_permission(actor, code: str) -> None:
    """Enforce a sensitive sale permission (system/None actors bypass)."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return
    if actor.is_superuser:
        return
    if code not in actor.effective_permission_codes:
        raise APIError(
            "PERMISSION_DENIED",
            f"Permission {code} is required for this sale.",
            status_code=403,
        )


def _enforce_sale_controls(*, customer, draft_items, expanded, actor) -> None:
    """Authoritative checks for overrides/pricing, run before any posting."""
    if any(item.is_free_goods for item in draft_items):
        _require_sale_permission(actor, "SALE_FREE_GOODS")

    projected_total = Decimal("0")
    for item, batch, take in expanded:
        share = take / item.qty if item.qty else Decimal("0")
        gross = money(take * item.unit_price)
        discount = money(item.line_discount * share)
        vat_amount = money(item.vat_amount * share)
        projected_total += gross - discount + vat_amount

        if item.is_free_goods:
            continue
        resolved = resolve_unit_price(item.medicine, customer)
        if cost4(item.unit_price) != cost4(resolved):
            _require_sale_permission(actor, "SALE_PRICE_OVERRIDE")
        if item.unit_price < batch.unit_cost:
            _require_sale_permission(actor, "SALE_BELOW_COST")

    if projected_total <= 0:
        _require_sale_permission(actor, "SALE_ZERO_VALUE")


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
    prior_advance_balance = customer_balance_from_ledger(customer)
    if customer.credit_hold:
        raise APIError(
            "CUSTOMER_ON_HOLD",
            "Customer is on credit hold; new sales are blocked.",
            status_code=409,
        )

    block_days = getattr(settings, "CUSTOMER_OVERDUE_BLOCK_DAYS", 30)
    from apps.common.settings_service import get_setting_value

    block_days = int(
        get_setting_value("CUSTOMER_OVERDUE_BLOCK_DAYS", default=block_days) or block_days
    )
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
        if item.batch is not None:
            # Explicit batch selection (FEFO override) captured on the draft.
            batch = MedicineBatch.objects.select_for_update().get(id=item.batch_id)
            if batch.branch_id != invoice.branch_id or batch.medicine_id != item.medicine_id:
                raise APIError("INVALID_BATCH", "Selected batch does not belong to this branch/medicine.")
            if batch.status != BatchStatus.ACTIVE:
                raise APIError("INVALID_BATCH", "Selected batch is not saleable.")
            if batch.expiry_date and batch.expiry_date < timezone.localdate():
                raise APIError("BATCH_EXPIRED", "Selected batch is expired.")
            allocations = [(batch, item.qty)]
        else:
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

    _enforce_sale_controls(
        customer=customer, draft_items=draft_items, expanded=expanded, actor=actor
    )

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

    if invoice.grand_total > 0:
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

    from apps.common.settings_service import get_setting_bool

    auto_apply = get_setting_bool(
        "AUTO_APPLY_ADVANCE", default=getattr(settings, "AUTO_APPLY_ADVANCE", False)
    )
    if auto_apply and prior_advance_balance < 0:
        applicable = min(-prior_advance_balance, invoice.grand_total - invoice.paid_total)
        if applicable > 0:
            post_customer_ledger_entry(
                customer=customer,
                branch=invoice.branch,
                entry_type=CustomerLedgerEntryType.ADVANCE_APPLIED,
                amount_delta=money(applicable),
                source_type="SALES_INVOICE",
                source_id=invoice.id,
                source_number=invoice.number,
                business_date=invoice.business_date,
                actor=actor,
            )
            invoice.paid_total = money(invoice.paid_total + applicable)
            invoice.payment_status = (
                SalesPaymentStatus.PAID
                if invoice.paid_total >= invoice.grand_total
                else SalesPaymentStatus.PARTIALLY_PAID
            )
            invoice.save(update_fields=["paid_total", "payment_status", "updated_at"])

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
def mark_invoice_delivered(*, invoice: SalesInvoice, actor) -> SalesInvoice:
    invoice = SalesInvoice.objects.select_for_update().get(id=invoice.id)
    if invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only confirmed invoices can be delivered.")
    if invoice.fulfillment_status == "DELIVERED":
        return invoice
    invoice.fulfillment_status = "DELIVERED"
    invoice.delivered_at = timezone.now()
    invoice.delivered_by = actor if getattr(actor, "is_authenticated", False) else None
    invoice.save(update_fields=["fulfillment_status", "delivered_at", "delivered_by", "updated_at"])
    return invoice


@transaction.atomic
def cancel_sale(*, invoice: SalesInvoice, actor, reason: str = "", idempotency_key: str | None = None) -> SalesInvoice:
    invoice = (
        SalesInvoice.objects.select_for_update()
        .select_related("customer", "branch")
        .get(id=invoice.id)
    )
    if idempotency_key and invoice.idempotency_key == idempotency_key:
        return invoice
    if invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only confirmed invoices can be cancelled.")
    if invoice.paid_total > 0:
        raise APIError(
            "INVOICE_HAS_PAYMENTS",
            "Reverse receipts before cancelling; or process a sales return.",
            status_code=409,
        )
    if invoice.return_status != SalesReturnStatus.NONE:
        raise APIError(
            "INVOICE_HAS_RETURNS",
            "Invoices with returns cannot be cancelled. Reverse the return or cancel the remaining lines.",
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

    if invoice.grand_total > 0:
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
    invoice.idempotency_key = idempotency_key or invoice.idempotency_key
    invoice.save(update_fields=["lifecycle", "cancel_reason", "idempotency_key", "updated_at"])
    return invoice


# --------------------------------------------------------------------------- sales returns


@transaction.atomic
def create_sales_return(
    *,
    invoice: SalesInvoice,
    reason_code: str,
    refund_method: str,
    refund_account=None,
    business_date=None,
    notes: str = "",
    items_data: list[dict],
    actor=None,
    idempotency_key: str | None = None,
) -> SalesReturn:
    invoice = (
        SalesInvoice.objects.select_for_update()
        .select_related("customer", "branch")
        .get(id=invoice.id)
    )
    if invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only confirmed invoices can be returned.")
    if idempotency_key:
        existing_return = SalesReturn.objects.filter(idempotency_key=idempotency_key).first()
        if existing_return is not None:
            return existing_return
    if refund_method in (RefundMethod.CASH, RefundMethod.BANK):
        if refund_account is None:
            raise APIError(
                "REFUND_ACCOUNT_REQUIRED", "A refund account is required for cash/bank refunds."
            )
        _require_sale_permission(actor, "RETURN_REFUND")

    sales_return = SalesReturn.objects.create(
        invoice=invoice,
        customer=invoice.customer,
        branch=invoice.branch,
        business_date=business_date or timezone.localdate(),
        reason_code=reason_code,
        refund_method=refund_method,
        refund_account=refund_account,
        notes=notes,
    )

    seen: set = set()
    for row in items_data:
        item = SalesInvoiceItem.objects.select_for_update().get(id=row["invoice_item"])
        if item.invoice_id != invoice.id:
            raise APIError("INVALID_RETURN_LINE", "Return line does not belong to the invoice.")
        if item.id in seen:
            raise APIError("DUPLICATE_RETURN_LINE", "Duplicate return lines are not allowed.")
        seen.add(item.id)
        if item.batch_id is None:
            raise APIError("INVALID_RETURN_LINE", "Invoice line has no batch.")
        qty = Decimal(row["qty"])
        if qty > item.returnable_qty:
            raise APIError(
                "RETURN_EXCEEDS_SALE",
                f"Line {item.line_no}: max returnable is {item.returnable_qty}.",
                status_code=409,
            )
        SalesReturnItem.objects.create(
            sales_return=sales_return,
            invoice_item=item,
            batch=item.batch,
            qty=qty,
            condition=row["condition"],
        )
    sales_return.idempotency_key = idempotency_key or sales_return.idempotency_key
    sales_return.save(update_fields=["idempotency_key", "updated_at"])
    return sales_return


@transaction.atomic
def create_direct_return(
    *,
    customer: Customer,
    branch,
    reason_code: str,
    refund_method: str,
    refund_account=None,
    business_date=None,
    notes: str = "",
    items_data: list[dict],
    actor=None,
    idempotency_key: str | None = None,
) -> SalesReturn:
    """Return without an original invoice (SRET_NO_INVOICE)."""
    if not items_data:
        raise APIError("EMPTY_RETURN", "A sales return must have at least one line.")
    _require_sale_permission(actor, "SRET_NO_INVOICE")

    if idempotency_key:
        existing = SalesReturn.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    if refund_method in (RefundMethod.CASH, RefundMethod.BANK):
        if refund_account is None:
            raise APIError(
                "REFUND_ACCOUNT_REQUIRED", "A refund account is required for cash/bank refunds."
            )
        _require_sale_permission(actor, "RETURN_REFUND")

    sales_return = SalesReturn.objects.create(
        invoice=None,
        customer=customer,
        branch=branch,
        business_date=business_date or timezone.localdate(),
        reason_code=reason_code,
        refund_method=refund_method,
        refund_account=refund_account,
        notes=notes,
    )

    for row in items_data:
        batch = row["batch"]
        medicine = row["medicine"]
        if batch.branch_id != branch.id:
            raise APIError("INVALID_BATCH", "Return batch does not belong to this branch.")
        if str(batch.medicine_id) != str(medicine.id):
            raise APIError("INVALID_BATCH", "Batch does not belong to the selected medicine.")
        unit_price = row.get("unit_price")
        if unit_price is None:
            unit_price = resolve_unit_price(medicine, customer)
        SalesReturnItem.objects.create(
            sales_return=sales_return,
            invoice_item=None,
            batch=batch,
            qty=Decimal(row["qty"]),
            condition=row["condition"],
            unit_price=cost4(unit_price),
            unit_cost=batch.unit_cost,
        )

    sales_return.idempotency_key = idempotency_key or sales_return.idempotency_key
    sales_return.save(update_fields=["idempotency_key", "updated_at"])
    return sales_return


@transaction.atomic
def confirm_sales_return(*, sales_return: SalesReturn, actor, idempotency_key: str | None = None) -> SalesReturn:
    sales_return = (
        SalesReturn.objects.select_for_update(of=("self",))
        .select_related("invoice", "customer", "branch")
        .get(id=sales_return.id)
    )
    if idempotency_key and sales_return.idempotency_key == idempotency_key:
        return sales_return
    if sales_return.status == SalesReturnDocStatus.CONFIRMED:
        return sales_return
    if sales_return.status != SalesReturnDocStatus.DRAFT:
        raise APIError("INVALID_STATUS_TRANSITION", "Only draft returns can be confirmed.")
    if sales_return.refund_method in (RefundMethod.CASH, RefundMethod.BANK):
        _require_sale_permission(actor, "RETURN_REFUND")

    items = list(sales_return.items.select_related("invoice_item", "batch__medicine"))
    if not items:
        raise APIError("EMPTY_RETURN", "A sales return must have at least one line.")

    today = timezone.localdate()
    movement_lines: list[MovementLine] = []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    vat_total = Decimal("0")

    for ret_item in items:
        invoice_item = None
        if ret_item.invoice_item_id:
            invoice_item = SalesInvoiceItem.objects.select_for_update().get(
                id=ret_item.invoice_item_id
            )
            if ret_item.qty > invoice_item.returnable_qty:
                raise APIError(
                    "RETURN_EXCEEDS_SALE",
                    f"Line {invoice_item.line_no}: max returnable is {invoice_item.returnable_qty}.",
                    status_code=409,
                )
            share = ret_item.qty / invoice_item.qty if invoice_item.qty else Decimal("0")
            discount_share = money(invoice_item.line_discount * share)
            vat_share = money(invoice_item.vat_amount * share)
            ret_item.unit_price = invoice_item.unit_price
            ret_item.unit_cost = invoice_item.unit_cost
        else:
            discount_share = Decimal("0")
            vat_share = Decimal("0")

        restock = (
            ret_item.condition == ReturnCondition.RESELLABLE
            and (ret_item.batch.expiry_date is None or ret_item.batch.expiry_date >= today)
            and ret_item.batch.status != BatchStatus.RECALLED
        )

        ret_item.discount_reversal = discount_share
        ret_item.vat_reversal = vat_share
        ret_item.restocked = restock
        ret_item.save(
            update_fields=[
                "unit_price",
                "discount_reversal",
                "vat_reversal",
                "unit_cost",
                "restocked",
                "updated_at",
            ]
        )

        subtotal += money(ret_item.qty * ret_item.unit_price)
        discount_total += discount_share
        vat_total += vat_share
        movement_lines.append(
            MovementLine(
                medicine=ret_item.batch.medicine,
                batch=ret_item.batch,
                qty_delta=ret_item.qty,
                unit_cost=ret_item.unit_cost,
                pool=StockPool.SALEABLE if restock else StockPool.QUARANTINE,
            )
        )

        if invoice_item is not None:
            invoice_item.returned_qty = invoice_item.returned_qty + ret_item.qty
            invoice_item.save(update_fields=["returned_qty", "updated_at"])

    net_total = money(subtotal - discount_total + vat_total)
    grand_total = net_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sales_return.subtotal = money(subtotal)
    sales_return.discount_reversal = money(discount_total)
    sales_return.vat_reversal = money(vat_total)
    sales_return.round_off = money(grand_total - net_total)
    sales_return.grand_total = money(grand_total)
    sales_return.number = allocate_number(
        branch=sales_return.branch,
        doc_type=DocumentType.CREDIT_NOTE,
        business_date=sales_return.business_date,
    )
    sales_return.status = SalesReturnDocStatus.CONFIRMED
    sales_return.confirmed_at = timezone.now()
    sales_return.confirmed_by = actor if getattr(actor, "is_authenticated", False) else None
    sales_return.idempotency_key = idempotency_key or sales_return.idempotency_key
    sales_return.save()

    post_transactions(
        branch=sales_return.branch,
        lines=movement_lines,
        entry_type=EntryType.SALES_RETURN,
        source_type="SALES_RETURN",
        source_id=sales_return.id,
        source_number=sales_return.number,
        business_date=sales_return.business_date,
        actor=actor,
    )
    if sales_return.grand_total > 0:
        post_customer_ledger_entry(
            customer=sales_return.customer,
            branch=sales_return.branch,
            entry_type=CustomerLedgerEntryType.SALES_RETURN,
            amount_delta=-sales_return.grand_total,
            source_type="SALES_RETURN",
            source_id=sales_return.id,
            source_number=sales_return.number,
            business_date=sales_return.business_date,
            actor=actor,
        )

    if sales_return.grand_total > 0 and sales_return.refund_method in (
        RefundMethod.CASH,
        RefundMethod.BANK,
    ):
        # The return credit is settled by the refund payment.
        post_customer_ledger_entry(
            customer=sales_return.customer,
            branch=sales_return.branch,
            entry_type=CustomerLedgerEntryType.ADVANCE_REFUND,
            amount_delta=sales_return.grand_total,
            source_type="SALES_RETURN",
            source_id=sales_return.id,
            source_number=sales_return.number,
            business_date=sales_return.business_date,
            actor=actor,
        )
        post_account_transaction(
            account=sales_return.refund_account,
            entry_type=FinancialEntryType.REFUND,
            amount_delta=-sales_return.grand_total,
            source_type="SALES_RETURN",
            source_id=sales_return.id,
            source_number=sales_return.number,
            business_date=sales_return.business_date,
            actor=actor,
        )

    if sales_return.invoice_id:
        invoice = SalesInvoice.objects.select_for_update().get(id=sales_return.invoice_id)
        invoice.returned_total = money(invoice.returned_total + sales_return.grand_total)
        any_returnable = any(item.returnable_qty > 0 for item in invoice.items.all())
        invoice.return_status = (
            SalesReturnStatus.FULLY_RETURNED
            if not any_returnable
            else SalesReturnStatus.PARTIALLY_RETURNED
        )
        invoice.save(update_fields=["returned_total", "return_status", "updated_at"])
    return sales_return
