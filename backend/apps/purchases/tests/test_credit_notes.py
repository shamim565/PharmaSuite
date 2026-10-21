"""Tests for supplier credit notes: create, settle via ledger, cancel."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import APIError
from apps.purchases.credit_models import SupplierCreditNoteReason, SupplierCreditNoteStatus
from apps.purchases.credit_services import (
    cancel_supplier_credit_note,
    create_supplier_credit_note,
    settle_supplier_credit_note,
)
from apps.suppliers.models import SupplierLedgerEntry, SupplierLedgerEntryType

pytestmark = pytest.mark.django_db


def _create_note(branch, supplier, actor, amount="500.00"):
    return create_supplier_credit_note(
        branch=branch,
        supplier=supplier,
        business_date=timezone.localdate(),
        amount=Decimal(amount),
        reason_code=SupplierCreditNoteReason.EXPIRY_RETURN,
        reference="SUP-CN-01",
        actor=actor,
    )


def test_create_credit_note_allocates_number_and_stays_open(branch, supplier, actor):
    note = _create_note(branch, supplier, actor)
    assert note.number
    assert note.number.startswith("SCN-")
    assert note.status == SupplierCreditNoteStatus.OPEN
    assert note.amount == Decimal("500.00")
    assert note.days_open == 0


def test_settle_credit_note_reduces_supplier_payable(branch, supplier, actor):
    note = _create_note(branch, supplier, actor)
    note = settle_supplier_credit_note(credit_note=note, actor=actor)

    assert note.status == SupplierCreditNoteStatus.SETTLED
    assert note.settled_at is not None

    entry = SupplierLedgerEntry.objects.get(source_type="SUPPLIER_CREDIT_NOTE", source_id=note.id)
    assert entry.entry_type == SupplierLedgerEntryType.CREDIT_NOTE
    assert entry.amount_delta == Decimal("-500.00")


def test_credit_note_can_only_be_settled_once(branch, supplier, actor):
    note = _create_note(branch, supplier, actor)
    settle_supplier_credit_note(credit_note=note, actor=actor)
    note.refresh_from_db()

    with pytest.raises(APIError):
        settle_supplier_credit_note(credit_note=note, actor=actor)


def test_cancel_open_credit_note(branch, supplier, actor):
    note = _create_note(branch, supplier, actor)
    note = cancel_supplier_credit_note(credit_note=note, actor=actor, reason="Issued in error")
    assert note.status == SupplierCreditNoteStatus.CANCELLED
    assert not SupplierLedgerEntry.objects.filter(source_id=note.id).exists()
