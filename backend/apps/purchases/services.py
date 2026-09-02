"""Purchase, supplier-payment and purchase-return services.

All confirm/pay/reverse/return operations are atomic and run inside a single
database transaction; stock goes through the inventory posting service and
money through the account ledger service.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.accounting.models import FinancialEntryType, FinancialTransaction
from apps.accounting.services import post_account_transaction
from apps.catalog.models import BatchStatus, MedicineBatch
from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.common.settings_service import get_setting_bool
from apps.inventory.models import EntryType
from apps.inventory.services import MovementLine, post_transactions
from apps.purchases.models import (
    Purchase,
    PurchaseItem,
    PurchasePaymentStatus,
    PurchaseReturn,
    PurchaseReturnDocStatus,
    PurchaseReturnStatus,
    PurchaseStatus,
    SupplierPayment,
    SupplierPaymentAllocation,
    SupplierPaymentStatus,
)
from apps.suppliers.models import Supplier, SupplierLedgerEntry, SupplierLedgerEntryType
from apps.suppliers.services import post_ledger_entry

TWO = Decimal("0.01")
FOUR = Decimal("0.0001")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def cost4(value) -> Decimal:
    return Decimal(value).quantize(FOUR, rounding=ROUND_HALF_UP)


def compute_line_totals(item: dict) -> dict:
    """Compute derived amounts for a purchase line input."""
    qty = Decimal(item["qty_entered"])
    bonus = Decimal(item.get("bonus_qty_entered") or 0)
    factor = Decimal(item.get("conversion_factor") or 1)
    unit_cost = Decimal(item["unit_cost"])
    discount = money(item.get("line_discount") or 0)
    vat_rate = Decimal(item.get("vat_rate") if item.get("vat_rate") is not None else 15)
    if not get_setting_bool("PURCHASE_VAT_ENABLED", default=False):
        vat_rate = Decimal("0")

    qty_base = (qty * factor).quantize(Decimal("0.001"))
    bonus_base = (bonus * factor).quantize(Decimal("0.001"))
    gross = money(qty * unit_cost)
    taxable = money(gross - discount)
    vat_amount = money(taxable * vat_rate / Decimal("100"))
    base_unit_cost = cost4(taxable / qty_base) if qty_base > 0 else Decimal("0")
    total_base = qty_base + bonus_base
    effective_unit_cost = cost4(taxable / total_base) if total_base > 0 else base_unit_cost

    return {
        "qty_base": qty_base,
        "bonus_qty_base": bonus_base,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "line_net": taxable,
        "base_unit_cost": base_unit_cost,
        "effective_unit_cost": effective_unit_cost,
    }


def compute_purchase_totals(line_results: list[dict], freight: Decimal = Decimal("0")) -> dict:
    subtotal = sum((row["gross"] for row in line_results), Decimal("0"))
    discount_total = sum((row["line_discount"] for row in line_results), Decimal("0"))
    vat_total = sum((row["vat_amount"] for row in line_results), Decimal("0"))
    net_total = money(subtotal - discount_total + vat_total + freight)
    grand_total = net_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {
        "subtotal": money(subtotal),
        "discount_total": money(discount_total),
        "vat_total": money(vat_total),
        "freight_total": money(freight),
        "round_off": money(grand_total - net_total),
        "grand_total": money(grand_total),
    }


def _get_or_create_batch(purchase: Purchase, item: PurchaseItem) -> MedicineBatch:
    batch = (
        MedicineBatch.objects.select_for_update()
        .filter(
            branch=purchase.branch,
            medicine=item.medicine,
            batch_number=item.batch_number,
            expiry_date=item.expiry_date,
        )
        .first()
    )
    if batch is not None:
        return batch

    status = BatchStatus.ACTIVE
    if item.expiry_date and item.expiry_date < timezone.localdate():
        status = BatchStatus.EXPIRED
    return MedicineBatch.objects.create(
        branch=purchase.branch,
        medicine=item.medicine,
        batch_number=item.batch_number,
        manufacturing_date=item.manufacturing_date,
        expiry_date=item.expiry_date,
        unit_cost=item.effective_unit_cost,
        status=status,
    )


@transaction.atomic
def confirm_purchase(
    *,
    purchase: Purchase,
    actor,
    allow_duplicate_invoice: bool = False,
    duplicate_reason: str = "",
    payment: dict | None = None,
    idempotency_key: str | None = None,
) -> Purchase:
    purchase = (
        Purchase.objects.select_for_update()
        .select_related("supplier", "branch")
        .get(id=purchase.id)
    )

    if purchase.lifecycle == PurchaseStatus.CONFIRMED:
        return purchase
    if purchase.lifecycle != PurchaseStatus.DRAFT:
        raise APIError("INVALID_STATUS_TRANSITION", "Only draft purchases can be confirmed.")

    if idempotency_key:
        existing = Purchase.objects.filter(idempotency_key=idempotency_key).exclude(id=purchase.id).first()
        if existing is not None:
            return existing

    if not allow_duplicate_invoice:
        duplicate = (
            Purchase.objects.filter(
                supplier=purchase.supplier,
                supplier_invoice_number__iexact=purchase.supplier_invoice_number,
                lifecycle=PurchaseStatus.CONFIRMED,
            )
            .exclude(id=purchase.id)
            .exists()
        )
        if duplicate:
            raise APIError(
                "DUPLICATE_SUPPLIER_INVOICE",
                "A confirmed purchase with this supplier invoice number already exists.",
                status_code=409,
            )
    else:
        purchase.duplicate_invoice_override = True
        purchase.duplicate_invoice_reason = duplicate_reason

    items = list(purchase.items.select_related("medicine").order_by("line_no"))
    if not items:
        raise APIError("EMPTY_PURCHASE", "A purchase must have at least one line.")

    purchase.number = allocate_number(
        branch=purchase.branch,
        doc_type=DocumentType.PURCHASE,
        business_date=purchase.business_date,
    )

    purchase_lines: list[MovementLine] = []
    bonus_lines: list[MovementLine] = []
    batch_increments: dict[UUID, Decimal] = {}

    for item in items:
        batch = _get_or_create_batch(purchase, item)
        item.batch = batch
        item.save(update_fields=["batch", "updated_at"])

        if item.qty_base > 0:
            purchase_lines.append(
                MovementLine(
                    medicine=item.medicine,
                    batch=batch,
                    qty_delta=item.qty_base,
                    unit_cost=item.effective_unit_cost,
                )
            )
        if item.bonus_qty_base > 0:
            bonus_lines.append(
                MovementLine(
                    medicine=item.medicine,
                    batch=batch,
                    qty_delta=item.bonus_qty_base,
                    unit_cost=item.effective_unit_cost,
                )
            )
        batch_increments[batch.id] = (
            batch_increments.get(batch.id, Decimal("0")) + item.qty_base + item.bonus_qty_base
        )

    if purchase_lines:
        post_transactions(
            branch=purchase.branch,
            lines=purchase_lines,
            entry_type=EntryType.PURCHASE,
            source_type="PURCHASE",
            source_id=purchase.id,
            source_number=purchase.number,
            business_date=purchase.business_date,
            actor=actor,
        )
    if bonus_lines:
        post_transactions(
            branch=purchase.branch,
            lines=bonus_lines,
            entry_type=EntryType.BONUS,
            source_type="PURCHASE",
            source_id=purchase.id,
            source_number=purchase.number,
            business_date=purchase.business_date,
            actor=actor,
        )

    for batch_id, extra in batch_increments.items():
        batch = MedicineBatch.objects.select_for_update().get(id=batch_id)
        batch.qty_received_total = batch.qty_received_total + extra
        batch.save(update_fields=["qty_received_total", "updated_at"])

    due_date = purchase.business_date + timedelta(days=purchase.supplier.credit_days)
    post_ledger_entry(
        supplier=purchase.supplier,
        branch=purchase.branch,
        entry_type=SupplierLedgerEntryType.PURCHASE,
        amount_delta=purchase.grand_total,
        source_type="PURCHASE",
        source_id=purchase.id,
        source_number=purchase.number,
        due_date=due_date,
        business_date=purchase.business_date,
        actor=actor,
    )

    purchase.lifecycle = PurchaseStatus.CONFIRMED
    purchase.confirmed_at = timezone.now()
    purchase.confirmed_by = actor if getattr(actor, "is_authenticated", False) else None
    purchase.idempotency_key = idempotency_key or purchase.idempotency_key
    purchase.save()

    if payment and Decimal(payment["amount"]) > 0:
        record_supplier_payment(
            supplier=purchase.supplier,
            branch=purchase.branch,
            amount=Decimal(payment["amount"]),
            method=payment["method"],
            account=payment["account"],
            business_date=purchase.business_date,
            reference=payment.get("reference", ""),
            allocations=[{"purchase": purchase, "amount": min(Decimal(payment["amount"]), purchase.outstanding)}],
            actor=actor,
            idempotency_key=f"confirm-pay:{purchase.id}",
        )

    purchase.refresh_from_db()
    return purchase


def models_f_increment(value):
    """Placeholder to keep the batch increment expression readable."""
    return value


@transaction.atomic
def cancel_purchase(*, purchase: Purchase, actor, reason: str = "", idempotency_key: str | None = None) -> Purchase:
    purchase = Purchase.objects.select_for_update().select_related("supplier", "branch").get(id=purchase.id)
    if purchase.lifecycle != PurchaseStatus.CONFIRMED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only confirmed purchases can be cancelled.")
    if purchase.paid_total > 0:
        raise APIError("PURCHASE_HAS_PAYMENTS", "Reverse supplier payments before cancelling.", status_code=409)
    if purchase.returned_total > 0:
        raise APIError("PURCHASE_HAS_RETURNS", "Purchases with returns cannot be cancelled.", status_code=409)

    items = list(purchase.items.select_related("medicine", "batch"))
    locked_batches: dict[UUID, MedicineBatch] = {}
    decrements: dict[UUID, Decimal] = {}

    for item in items:
        if item.batch is None:
            continue
        batch = locked_batches.get(item.batch_id)
        if batch is None:
            batch = MedicineBatch.objects.select_for_update().get(id=item.batch_id)
            locked_batches[item.batch_id] = batch
        total_out = item.qty_base + item.bonus_qty_base
        if batch.qty_on_hand < total_out:
            raise APIError(
                "PURCHASE_STOCK_CONSUMED",
                f"Stock from batch {batch.batch_number} has been consumed; use a purchase return instead.",
                status_code=409,
            )
        decrements[item.batch_id] = decrements.get(item.batch_id, Decimal("0")) + total_out

    reversal_lines = [
        MovementLine(
            medicine=item.medicine,
            batch=item.batch,
            qty_delta=-(item.qty_base + item.bonus_qty_base),
            unit_cost=item.effective_unit_cost,
        )
        for item in items
        if item.batch is not None and (item.qty_base + item.bonus_qty_base) > 0
    ]
    if reversal_lines:
        post_transactions(
            branch=purchase.branch,
            lines=reversal_lines,
            entry_type=EntryType.REVERSAL,
            source_type="PURCHASE_CANCEL",
            source_id=purchase.id,
            source_number=purchase.number or "",
            business_date=timezone.localdate(),
            actor=actor,
        )

    for batch_id, total_out in decrements.items():
        batch = locked_batches[batch_id]
        batch.qty_received_total = max(batch.qty_received_total - total_out, Decimal("0"))
        batch.save(update_fields=["qty_received_total", "updated_at"])

    post_ledger_entry(
        supplier=purchase.supplier,
        branch=purchase.branch,
        entry_type=SupplierLedgerEntryType.ADJUSTMENT,
        amount_delta=-purchase.grand_total,
        source_type="PURCHASE_CANCEL",
        source_id=purchase.id,
        source_number=purchase.number or "",
        business_date=timezone.localdate(),
        actor=actor,
    )

    purchase.lifecycle = PurchaseStatus.CANCELLED
    purchase.cancel_reason = reason
    purchase.idempotency_key = idempotency_key or purchase.idempotency_key
    purchase.save(update_fields=["lifecycle", "cancel_reason", "updated_at"])
    return purchase


@transaction.atomic
def record_supplier_payment(
    *,
    supplier: Supplier,
    branch,
    amount: Decimal,
    method: str,
    account,
    business_date=None,
    reference: str = "",
    allocations: list[dict] | None = None,
    actor=None,
    idempotency_key: str | None = None,
) -> SupplierPayment:
    supplier = Supplier.objects.select_for_update().get(id=supplier.id)

    if idempotency_key:
        existing = SupplierPayment.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    amount = Decimal(amount)
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Payment amount must be positive.")

    business_date = business_date or timezone.localdate()
    open_purchases = list(
        Purchase.objects.select_for_update()
        .filter(supplier=supplier, lifecycle=PurchaseStatus.CONFIRMED)
        .order_by("business_date", "created_at")
    )
    open_purchases = [p for p in open_purchases if (p.grand_total - p.paid_total) > 0]

    if allocations is None:
        remaining = amount
        allocations = []
        for purchase in open_purchases:
            if remaining <= 0:
                break
            outstanding = purchase.grand_total - purchase.paid_total
            take = min(remaining, outstanding)
            if take > 0:
                allocations.append({"purchase": purchase, "amount": take})
                remaining -= take
    else:
        normalized = []
        for allocation in allocations:
            purchase = Purchase.objects.select_for_update().get(id=allocation["purchase"].id)
            if purchase.supplier_id != supplier.id or purchase.lifecycle != PurchaseStatus.CONFIRMED:
                raise APIError("INVALID_PURCHASE", "Allocation references an invalid purchase.")
            outstanding = purchase.grand_total - purchase.paid_total
            alloc_amount = Decimal(allocation["amount"])
            if alloc_amount > outstanding:
                raise APIError(
                    "PAYMENT_EXCEEDS_BALANCE",
                    f"Allocation exceeds outstanding {outstanding} for purchase {purchase.number}.",
                    status_code=409,
                )
            normalized.append({"purchase": purchase, "amount": alloc_amount})
        allocations = normalized

    allocated_total = sum((a["amount"] for a in allocations), Decimal("0"))
    if allocated_total > amount:
        raise APIError("ALLOCATION_EXCEEDS_PAYMENT", "Allocations exceed the payment amount.")

    payment = SupplierPayment.objects.create(
        number=allocate_number(
            branch=branch, doc_type=DocumentType.SUPPLIER_PAYMENT, business_date=business_date
        ),
        branch=branch,
        supplier=supplier,
        business_date=business_date,
        amount=money(amount),
        method=method,
        account=account,
        reference=reference,
        idempotency_key=idempotency_key,
    )

    for allocation in allocations:
        purchase = allocation["purchase"]
        SupplierPaymentAllocation.objects.create(
            payment=payment, purchase=purchase, amount=money(allocation["amount"])
        )
        purchase.paid_total = money(purchase.paid_total + allocation["amount"])
        if purchase.paid_total >= purchase.grand_total:
            purchase.payment_status = PurchasePaymentStatus.PAID
        elif purchase.paid_total > 0:
            purchase.payment_status = PurchasePaymentStatus.PARTIALLY_PAID
        purchase.save(update_fields=["paid_total", "payment_status", "updated_at"])

    post_account_transaction(
        account=account,
        entry_type=FinancialEntryType.PURCHASE_PAYMENT,
        amount_delta=-money(amount),
        source_type="SUPPLIER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        reference=reference,
        business_date=business_date,
        actor=actor,
    )
    post_ledger_entry(
        supplier=supplier,
        branch=branch,
        entry_type=SupplierLedgerEntryType.PAYMENT,
        amount_delta=-money(amount),
        source_type="SUPPLIER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        business_date=business_date,
        actor=actor,
    )
    return payment


@transaction.atomic
def reverse_supplier_payment(*, payment: SupplierPayment, actor, reason: str = "", idempotency_key: str | None = None) -> SupplierPayment:
    payment = (
        SupplierPayment.objects.select_for_update()
        .select_related("supplier", "branch", "account")
        .get(id=payment.id)
    )
    if idempotency_key and payment.idempotency_key == idempotency_key:
        return payment
    if payment.status != SupplierPaymentStatus.ACTIVE:
        raise APIError("INVALID_STATUS_TRANSITION", "Only active payments can be reversed.")

    for allocation in payment.allocations.select_related("purchase"):
        purchase = Purchase.objects.select_for_update().get(id=allocation.purchase_id)
        purchase.paid_total = money(purchase.paid_total - allocation.amount)
        if purchase.paid_total <= 0:
            purchase.payment_status = PurchasePaymentStatus.UNPAID
        elif purchase.paid_total < purchase.grand_total:
            purchase.payment_status = PurchasePaymentStatus.PARTIALLY_PAID
        purchase.save(update_fields=["paid_total", "payment_status", "updated_at"])

    original_txn = FinancialTransaction.objects.filter(
        source_type="SUPPLIER_PAYMENT", source_id=payment.id
    ).first()
    post_account_transaction(
        account=payment.account,
        entry_type=FinancialEntryType.PAYMENT_REVERSAL,
        amount_delta=payment.amount,
        source_type="SUPPLIER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        reference=payment.reference,
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original_txn,
    )
    original_entry = SupplierLedgerEntry.objects.filter(
        source_type="SUPPLIER_PAYMENT", source_id=payment.id
    ).first()
    post_ledger_entry(
        supplier=payment.supplier,
        branch=payment.branch,
        entry_type=SupplierLedgerEntryType.PAYMENT_REVERSAL,
        amount_delta=payment.amount,
        source_type="SUPPLIER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original_entry,
    )

    payment.status = SupplierPaymentStatus.REVERSED
    payment.reversal_reason = reason
    payment.idempotency_key = idempotency_key or payment.idempotency_key
    payment.save(update_fields=["status", "reversal_reason", "idempotency_key", "updated_at"])
    return payment


@transaction.atomic
def confirm_purchase_return(*, purchase_return: PurchaseReturn, actor, idempotency_key: str | None = None) -> PurchaseReturn:
    purchase_return = (
        PurchaseReturn.objects.select_for_update()
        .select_related("purchase", "supplier", "branch")
        .get(id=purchase_return.id)
    )
    if purchase_return.status == PurchaseReturnDocStatus.CONFIRMED:
        return purchase_return
    if purchase_return.status != PurchaseReturnDocStatus.DRAFT:
        raise APIError("INVALID_STATUS_TRANSITION", "Only draft returns can be confirmed.")

    items = list(purchase_return.items.select_related("purchase_item__medicine", "batch"))
    if not items:
        raise APIError("EMPTY_RETURN", "A purchase return must have at least one line.")

    purchase = Purchase.objects.select_for_update().get(id=purchase_return.purchase_id)
    subtotal = Decimal("0")
    vat_total = Decimal("0")
    movement_lines: list[MovementLine] = []

    for item in items:
        purchase_item = PurchaseItem.objects.select_for_update().get(id=item.purchase_item_id)
        if item.qty > purchase_item.returnable_qty_base:
            raise APIError(
                "RETURN_EXCEEDS_PURCHASE",
                (
                    f"Return quantity {item.qty} exceeds returnable "
                    f"{purchase_item.returnable_qty_base} for line {purchase_item.line_no}."
                ),
                status_code=409,
            )

        base_cost = purchase_item.base_unit_cost or purchase_item.effective_unit_cost
        line_value = money(item.qty * base_cost)
        vat_share = (
            money(purchase_item.vat_amount * item.qty / purchase_item.qty_base)
            if purchase_item.qty_base > 0
            else Decimal("0")
        )
        item.unit_cost = base_cost
        item.vat_amount = vat_share
        item.line_total = money(line_value + vat_share)
        item.save(update_fields=["unit_cost", "vat_amount", "line_total", "updated_at"])

        purchase_item.returned_qty_base = purchase_item.returned_qty_base + item.qty
        purchase_item.save(update_fields=["returned_qty_base", "updated_at"])

        subtotal += line_value
        vat_total += vat_share
        movement_lines.append(
            MovementLine(
                medicine=purchase_item.medicine,
                batch=item.batch,
                qty_delta=-item.qty,
                unit_cost=item.batch.unit_cost,
            )
        )

    net_total = money(subtotal + vat_total)
    grand_total = net_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    purchase_return.subtotal = money(subtotal)
    purchase_return.vat_total = money(vat_total)
    purchase_return.round_off = money(grand_total - net_total)
    purchase_return.grand_total = money(grand_total)
    purchase_return.number = allocate_number(
        branch=purchase_return.branch,
        doc_type=DocumentType.DEBIT_NOTE,
        business_date=purchase_return.business_date,
    )
    purchase_return.status = PurchaseReturnDocStatus.CONFIRMED
    purchase_return.confirmed_at = timezone.now()
    purchase_return.confirmed_by = actor if getattr(actor, "is_authenticated", False) else None
    purchase_return.idempotency_key = idempotency_key or purchase_return.idempotency_key
    purchase_return.save()

    post_transactions(
        branch=purchase_return.branch,
        lines=movement_lines,
        entry_type=EntryType.PURCHASE_RETURN,
        source_type="PURCHASE_RETURN",
        source_id=purchase_return.id,
        source_number=purchase_return.number,
        business_date=purchase_return.business_date,
        actor=actor,
    )
    post_ledger_entry(
        supplier=purchase_return.supplier,
        branch=purchase_return.branch,
        entry_type=SupplierLedgerEntryType.PURCHASE_RETURN,
        amount_delta=-purchase_return.grand_total,
        source_type="PURCHASE_RETURN",
        source_id=purchase_return.id,
        source_number=purchase_return.number,
        business_date=purchase_return.business_date,
        actor=actor,
    )

    purchase.returned_total = money(purchase.returned_total + purchase_return.grand_total)
    any_remaining = any(
        pi.returnable_qty_base > 0 for pi in PurchaseItem.objects.filter(purchase=purchase)
    )
    purchase.return_status = (
        PurchaseReturnStatus.FULLY_RETURNED
        if not any_remaining
        else PurchaseReturnStatus.PARTIALLY_RETURNED
    )
    purchase.save(update_fields=["returned_total", "return_status", "updated_at"])
    return purchase_return
