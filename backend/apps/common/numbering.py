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
    DocumentType.TRANSFER: "TRF",
    DocumentType.EXPENSE: "EXP",
    DocumentType.INCOME: "INC",
}

PREFIX_SETTING_BY_DOC = {
    DocumentType.PURCHASE: "PURCHASE_PREFIX",
    DocumentType.SUPPLIER_PAYMENT: "SUPPLIER_PAYMENT_PREFIX",
    DocumentType.DEBIT_NOTE: "DEBIT_NOTE_PREFIX",
    DocumentType.SALES_INVOICE: "INVOICE_PREFIX",
    DocumentType.RECEIPT: "RECEIPT_PREFIX",
    DocumentType.CREDIT_NOTE: "CREDIT_NOTE_PREFIX",
    DocumentType.ADJUSTMENT: "ADJUSTMENT_PREFIX",
    DocumentType.TRANSFER: "TRANSFER_PREFIX",
    DocumentType.EXPENSE: "EXPENSE_PREFIX",
    DocumentType.INCOME: "INCOME_PREFIX",
}


def current_fiscal_year(business_date=None) -> int:
    """Bangladesh fiscal year runs July–June; returns the starting year (e.g., 2026 for FY2026-27)."""
    date = business_date or timezone.localdate()
    return date.year if date.month >= 7 else date.year - 1


def _locked_sequence(
    branch, doc_type: str, fiscal_year: int, prefix: str | None = None, width: int | None = None
) -> DocumentSequence:
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
                    prefix=prefix or PREFIXES[doc_type],
                    width=width or 6,
                )
        except IntegrityError:
            return DocumentSequence.objects.select_for_update().get(
                branch=branch, doc_type=doc_type, fiscal_year=fiscal_year
            )


def allocate_number(*, branch, doc_type: str, business_date=None) -> str:
    """Return the next document number, e.g. ``PUR-MAIN-26-000001``.

    Prefix/width come from company settings when present, otherwise the
    built-in mapping (existing sequences keep their historical prefix).
    """
    from apps.common.settings_service import get_setting_value

    prefix = get_setting_value(PREFIX_SETTING_BY_DOC.get(doc_type, "")) or PREFIXES[doc_type]
    width_raw = get_setting_value("DOCUMENT_NUMBER_WIDTH")
    width = int(width_raw) if width_raw not in (None, "") else None

    fiscal_year = current_fiscal_year(business_date)
    with transaction.atomic():
        sequence = _locked_sequence(branch, doc_type, fiscal_year, prefix=prefix, width=width)
        number = sequence.next_number
        sequence.next_number = number + 1
        sequence.save(update_fields=["next_number", "updated_at"])
    return f"{sequence.prefix}-{branch.code}-{fiscal_year % 100:02d}-{number:0{sequence.width}d}"
