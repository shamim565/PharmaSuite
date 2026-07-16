"""Gapless document numbering, safe under concurrency.

Allocation happens inside the caller's transaction: the sequence row is locked
with ``select_for_update`` and incremented only if the caller commits.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.models import DocumentSequence, DocumentType

PREFIXES = {
    DocumentType.PURCHASE: "PUR",
    DocumentType.SUPPLIER_PAYMENT: "PPV",
    DocumentType.DEBIT_NOTE: "DBN",
    DocumentType.SALES_INVOICE: "INV",
    DocumentType.RECEIPT: "RCP",
    DocumentType.CREDIT_NOTE: "CRN",
    DocumentType.ADJUSTMENT: "ADJ",
}


def current_fiscal_year(business_date=None) -> int:
    """Bangladesh fiscal year runs July–June; returns the starting year (e.g., 2026 for FY2026-27)."""
    date = business_date or timezone.localdate()
    return date.year if date.month >= 7 else date.year - 1


def _locked_sequence(branch, doc_type: str, fiscal_year: int) -> DocumentSequence:
    try:
        return DocumentSequence.objects.select_for_update().get(
            branch=branch, doc_type=doc_type, fiscal_year=fiscal_year
        )
    except DocumentSequence.DoesNotExist:
        try:
            with transaction.atomic():
                return DocumentSequence.objects.create(
                    branch=branch,
                    doc_type=doc_type,
                    fiscal_year=fiscal_year,
                    prefix=PREFIXES[doc_type],
                )
        except IntegrityError:
            return DocumentSequence.objects.select_for_update().get(
                branch=branch, doc_type=doc_type, fiscal_year=fiscal_year
            )


def allocate_number(*, branch, doc_type: str, business_date=None) -> str:
    """Return the next document number, e.g. ``PUR-MAIN-26-000001``."""
    fiscal_year = current_fiscal_year(business_date)
    with transaction.atomic():
        sequence = _locked_sequence(branch, doc_type, fiscal_year)
        number = sequence.next_number
        sequence.next_number = number + 1
        sequence.save(update_fields=["next_number", "updated_at"])
    return f"{sequence.prefix}-{branch.code}-{fiscal_year % 100:02d}-{number:0{sequence.width}d}"
