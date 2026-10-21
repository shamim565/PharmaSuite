from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.common.models import DocumentType
from apps.common.numbering import allocate_number
from apps.purchases.credit_models import (
    SupplierCreditNote,
    SupplierCreditNoteStatus,
)
from apps.suppliers.models import SupplierLedgerEntryType
from apps.suppliers.services import post_ledger_entry


def create_supplier_credit_note(
    *,
    branch,
    supplier,
    business_date,
    amount,
    reason_code,
    reference: str = "",
    notes: str = "",
    adjustment=None,
    actor=None,
    idempotency_key: str | None = None,
) -> SupplierCreditNote:
    """Create an OPEN supplier credit note and allocate its number."""
    with transaction.atomic():
        if idempotency_key:
            existing = SupplierCreditNote.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        note = SupplierCreditNote(
            branch=branch,
            supplier=supplier,
            business_date=business_date,
            amount=Decimal(amount),
            reason_code=reason_code,
            reference=reference,
            notes=notes,
            adjustment=adjustment,
            idempotency_key=idempotency_key,
        )
        note.full_clean()
        note.save()
        note.number = allocate_number(
            branch=branch, doc_type=DocumentType.SUPPLIER_CREDIT_NOTE, business_date=business_date
        )
        note.save(update_fields=["number", "updated_at"])
    return note


def settle_supplier_credit_note(*, credit_note: SupplierCreditNote, actor) -> SupplierCreditNote:
    """Settle the credit note: reduce the supplier payable via the ledger."""
    if credit_note.status != SupplierCreditNoteStatus.OPEN:
        raise APIError("INVALID_STATUS", "Only open credit notes can be settled.")
    with transaction.atomic():
        post_ledger_entry(
            supplier=credit_note.supplier,
            branch=credit_note.branch,
            entry_type=SupplierLedgerEntryType.CREDIT_NOTE,
            amount_delta=-credit_note.amount,
            source_type="SUPPLIER_CREDIT_NOTE",
            source_id=credit_note.id,
            source_number=credit_note.number,
            business_date=credit_note.business_date,
            actor=actor,
        )
        credit_note.status = SupplierCreditNoteStatus.SETTLED
        credit_note.settled_at = timezone.now()
        credit_note.settled_by = actor if getattr(actor, "is_authenticated", False) else None
        credit_note.save(
            update_fields=["status", "settled_at", "settled_by", "updated_at"]
        )
    return credit_note


def cancel_supplier_credit_note(*, credit_note: SupplierCreditNote, actor, reason: str = "") -> SupplierCreditNote:
    if credit_note.status != SupplierCreditNoteStatus.OPEN:
        raise APIError("INVALID_STATUS", "Only open credit notes can be cancelled.")
    credit_note.status = SupplierCreditNoteStatus.CANCELLED
    credit_note.cancel_reason = reason
    credit_note.save(update_fields=["status", "cancel_reason", "updated_at"])
    return credit_note
