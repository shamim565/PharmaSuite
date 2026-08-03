"""Customer receipt service — atomic payment, allocation, account and ledger posting."""

from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounting.models import FinancialEntryType, FinancialTransaction
from apps.accounting.services import post_account_transaction
from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.payments.models import (
    Cheque,
    ChequeDirection,
    ChequeStatus,
    Payment,
    PaymentAllocation,
    PaymentStatus,
)
from apps.sales.models import (
    Customer,
    CustomerLedgerEntry,
    CustomerLedgerEntryType,
    SalesInvoice,
    SalesInvoiceStatus,
    SalesPaymentStatus,
)
from apps.sales.services import money, post_customer_ledger_entry


@transaction.atomic
def record_customer_payment(
    *,
    customer: Customer,
    branch,
    amount: Decimal,
    method: str,
    account,
    business_date=None,
    reference: str = "",
    allocations: list[dict] | None = None,
    actor=None,
    collector=None,
    idempotency_key: str | None = None,
) -> Payment:
    customer = Customer.objects.select_for_update().get(id=customer.id)

    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    amount = money(amount)
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Payment amount must be positive.")

    business_date = business_date or timezone.localdate()
    open_invoices = list(
        SalesInvoice.objects.select_for_update()
        .filter(customer=customer, lifecycle=SalesInvoiceStatus.CONFIRMED)
        .order_by("business_date", "created_at")
    )
    open_invoices = [inv for inv in open_invoices if (inv.grand_total - inv.paid_total) > 0]

    if allocations is None:
        remaining = amount
        allocations = []
        for invoice in open_invoices:
            if remaining <= 0:
                break
            outstanding = invoice.grand_total - invoice.paid_total
            take = min(remaining, outstanding)
            if take > 0:
                allocations.append({"invoice": invoice, "amount": take})
                remaining -= take
    else:
        normalized = []
        for allocation in allocations:
            invoice = SalesInvoice.objects.select_for_update().get(id=allocation["invoice"].id)
            if invoice.customer_id != customer.id or invoice.lifecycle != SalesInvoiceStatus.CONFIRMED:
                raise APIError("INVALID_INVOICE", "Allocation references an invalid invoice.")
            outstanding = invoice.grand_total - invoice.paid_total
            alloc_amount = money(allocation["amount"])
            if alloc_amount > outstanding:
                raise APIError(
                    "PAYMENT_EXCEEDS_BALANCE",
                    f"Allocation exceeds outstanding {outstanding} for invoice {invoice.number}.",
                    status_code=409,
                )
            normalized.append({"invoice": invoice, "amount": alloc_amount})
        allocations = normalized

    allocated_total = sum((a["amount"] for a in allocations), Decimal("0"))
    if allocated_total > amount:
        raise APIError("ALLOCATION_EXCEEDS_PAYMENT", "Allocations exceed the payment amount.")

    group_id = uuid4()
    payment = Payment.objects.create(
        number=allocate_number(branch=branch, doc_type=DocumentType.RECEIPT, business_date=business_date),
        branch=branch,
        customer=customer,
        business_date=business_date,
        amount=amount,
        method=method,
        account=account,
        reference=reference,
        collector=collector or (actor if getattr(actor, "is_authenticated", False) else None),
        idempotency_key=idempotency_key,
    )

    for allocation in allocations:
        invoice = allocation["invoice"]
        PaymentAllocation.objects.create(
            payment=payment, invoice=invoice, amount=money(allocation["amount"])
        )
        invoice.paid_total = money(invoice.paid_total + allocation["amount"])
        if invoice.paid_total >= invoice.grand_total:
            invoice.payment_status = SalesPaymentStatus.PAID
        elif invoice.paid_total > 0:
            invoice.payment_status = SalesPaymentStatus.PARTIALLY_PAID
        invoice.save(update_fields=["paid_total", "payment_status", "updated_at"])

    post_account_transaction(
        account=account,
        entry_type=FinancialEntryType.SALE_RECEIPT,
        amount_delta=amount,
        source_type="CUSTOMER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        reference=reference,
        business_date=business_date,
        actor=actor,
        transaction_group_id=group_id,
    )
    post_customer_ledger_entry(
        customer=customer,
        branch=branch,
        entry_type=CustomerLedgerEntryType.PAYMENT,
        amount_delta=-amount,
        source_type="CUSTOMER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        business_date=business_date,
        actor=actor,
        transaction_group_id=group_id,
    )
    return payment


@transaction.atomic
def reverse_customer_payment(*, payment: Payment, actor, reason: str = "") -> Payment:
    payment = (
        Payment.objects.select_for_update()
        .select_related("customer", "branch", "account")
        .get(id=payment.id)
    )
    if payment.status != PaymentStatus.ACTIVE:
        raise APIError("INVALID_STATUS_TRANSITION", "Only active receipts can be reversed.")

    for allocation in payment.allocations.select_related("invoice"):
        invoice = SalesInvoice.objects.select_for_update().get(id=allocation.invoice_id)
        invoice.paid_total = money(invoice.paid_total - allocation.amount)
        if invoice.paid_total <= 0:
            invoice.payment_status = SalesPaymentStatus.UNPAID
        elif invoice.paid_total < invoice.grand_total:
            invoice.payment_status = SalesPaymentStatus.PARTIALLY_PAID
        invoice.save(update_fields=["paid_total", "payment_status", "updated_at"])

    original_txn = FinancialTransaction.objects.filter(
        source_type="CUSTOMER_PAYMENT", source_id=payment.id
    ).first()
    post_account_transaction(
        account=payment.account,
        entry_type=FinancialEntryType.RECEIPT_REVERSAL,
        amount_delta=-payment.amount,
        source_type="CUSTOMER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        reference=payment.reference,
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original_txn,
    )
    original_entry = CustomerLedgerEntry.objects.filter(
        source_type="CUSTOMER_PAYMENT", source_id=payment.id
    ).first()
    post_customer_ledger_entry(
        customer=payment.customer,
        branch=payment.branch,
        entry_type=CustomerLedgerEntryType.PAYMENT_REVERSAL,
        amount_delta=payment.amount,
        source_type="CUSTOMER_PAYMENT",
        source_id=payment.id,
        source_number=payment.number or "",
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original_entry,
    )

    payment.status = PaymentStatus.REVERSED
    payment.reversal_reason = reason
    payment.save(update_fields=["status", "reversal_reason", "updated_at"])
    return payment


# --------------------------------------------------------------------------- cheques


def _date_today():
    return timezone.localdate()


def create_cheque(*, validated, actor) -> Cheque:
    data = dict(validated)
    if data.get("customer") and data.get("supplier"):
        raise APIError("ONE_COUNTERPARTY", "A cheque has either a customer or a supplier, not both.")
    if not data.get("customer") and not data.get("supplier"):
        raise APIError("COUNTERPARTY_REQUIRED", "Specify the customer (received) or supplier (issued).")
    data["status"] = (
        ChequeStatus.PENDING_DEPOSIT
        if data.get("direction") == ChequeDirection.RECEIVED
        else ChequeStatus.PENDING
    )
    data["created_by"] = actor
    return Cheque.objects.create(**data)


def _transition(cheque: Cheque, allowed: set[str], target: str, *, date_field: str, actor, notes="") -> Cheque:
    if cheque.status not in allowed:
        raise APIError(
            "INVALID_CHEQUE_STATE",
            f"Cannot move cheque from {cheque.status} to {target}.",
            status_code=400,
        )
    cheque.status = target
    setattr(cheque, date_field, _date_today())
    if notes:
        cheque.notes = (cheque.notes + "\n" + notes).strip()
    cheque.save()
    return cheque


def deposit_cheque(cheque: Cheque, actor, notes="") -> Cheque:
    if cheque.direction != ChequeDirection.RECEIVED:
        raise APIError("INVALID_CHEQUE_STATE", "Only received cheques can be deposited.")
    return _transition(cheque, {ChequeStatus.PENDING_DEPOSIT}, ChequeStatus.DEPOSITED, date_field="date_deposited", actor=actor, notes=notes)


def clear_cheque(cheque: Cheque, actor, notes="") -> Cheque:
    if cheque.direction != ChequeDirection.RECEIVED:
        raise APIError("INVALID_CHEQUE_STATE", "Only received cheques can clear.")
    return _transition(cheque, {ChequeStatus.DEPOSITED}, ChequeStatus.CLEARED, date_field="date_cleared", actor=actor, notes=notes)


def bounce_cheque(cheque: Cheque, actor, notes="") -> Cheque:
    if cheque.direction != ChequeDirection.RECEIVED:
        raise APIError("INVALID_CHEQUE_STATE", "Only received cheques can bounce.")
    return _transition(cheque, {ChequeStatus.DEPOSITED, ChequeStatus.PENDING_DEPOSIT}, ChequeStatus.BOUNCED, date_field="date_bounced", actor=actor, notes=notes)


def stop_cheque(cheque: Cheque, actor, notes="") -> Cheque:
    return _transition(cheque, {ChequeStatus.PENDING_DEPOSIT, ChequeStatus.DEPOSITED, ChequeStatus.PENDING}, ChequeStatus.STOPPED, date_field="date_stopped", actor=actor, notes=notes)


def mark_cheque_paid(cheque: Cheque, actor, notes="") -> Cheque:
    if cheque.direction != ChequeDirection.ISSUED:
        raise APIError("INVALID_CHEQUE_STATE", "Only issued cheques can be marked paid.")
    return _transition(cheque, {ChequeStatus.PENDING}, ChequeStatus.PAID, date_field="date_paid", actor=actor, notes=notes)
