"""Company/branch settings read/write with a default fallback.

Settings are flat string keys (e.g. ``STOCK_ADJUSTMENT_APPROVAL_THRESHOLD``,
``numbering_prefix.SALES_INVOICE``). Company scope is a Setting row with
branch=null; a branch row overrides the company value.
"""

from decimal import Decimal, InvalidOperation

from apps.common.models import Setting

SETTINGS_KEYS: dict[str, tuple] = {
    # key: (category, label, default)
    "COMPANY_NAME": ("company", "Company name", ""),
    "COMPANY_ADDRESS": ("company", "Company address", ""),
    "COMPANY_PHONE": ("company", "Company phone", ""),
    "COMPANY_BIN": ("company", "BIN number", ""),
    "COMPANY_VAT_REG": ("company", "VAT registration", ""),
    "COMPANY_EMAIL": ("company", "Company email", ""),
    "EXPENSE_APPROVAL_THRESHOLD": ("approvals", "Expense approval threshold", "5000"),
    "STOCK_ADJUSTMENT_APPROVAL_THRESHOLD": ("approvals", "Stock adjustment approval threshold", "5000"),
    "CUSTOMER_OVERDUE_BLOCK_DAYS": ("credit", "Customer overdue block days", "30"),
    "AUTO_APPLY_ADVANCE": ("features", "Auto-apply customer advance at sale", False),
    "SALES_VAT_ENABLED": ("features", "Charge VAT on sales invoices", False),
    "PURCHASE_VAT_ENABLED": ("features", "Charge VAT on purchases", False),
    "NEAR_EXPIRY_DAYS": ("expiry", "Near-expiry warning days", "90"),
    "INVOICE_PREFIX": ("numbering", "Invoice prefix", "INV"),
    "RECEIPT_PREFIX": ("numbering", "Receipt prefix", "RCP"),
    "CREDIT_NOTE_PREFIX": ("numbering", "Credit note prefix", "CRN"),
    "SUPPLIER_CREDIT_NOTE_PREFIX": ("numbering", "Supplier credit note prefix", "SCN"),
    "DEBIT_NOTE_PREFIX": ("numbering", "Debit note prefix", "DBN"),
    "PURCHASE_PREFIX": ("numbering", "Purchase prefix", "PUR"),
    "SUPPLIER_PAYMENT_PREFIX": ("numbering", "Supplier payment prefix", "PPV"),
    "ADJUSTMENT_PREFIX": ("numbering", "Adjustment prefix", "ADJ"),
    "TRANSFER_PREFIX": ("numbering", "Stock transfer prefix", "TRF"),
    "EXPENSE_PREFIX": ("numbering", "Expense prefix", "EXP"),
    "INCOME_PREFIX": ("numbering", "Income prefix", "INC"),
    "DOCUMENT_NUMBER_WIDTH": ("numbering", "Document number width", 6),
    "SMS_GATEWAY_URL": ("notifications", "SMS gateway URL (JSON POST receives {to, text})", ""),
    "SMS_GATEWAY_TOKEN": ("notifications", "SMS gateway bearer token", ""),
}


def get_setting(key: str, branch=None, default=None):
    row = Setting.objects.filter(key=key, branch=branch).first()
    if row is None:
        row = Setting.objects.filter(key=key, branch__isnull=True).first()
    if row is None:
        return default
    return row["value"] if isinstance(row, dict) else row.value


def get_setting_value(key: str, branch=None, default=None):
    """Public read API returning a JSON-decodable value."""
    row = Setting.objects.filter(key=key, branch=branch).first() or Setting.objects.filter(
        key=key, branch__isnull=True
    ).first()
    if row is None:
        return default
    return row.value


def get_setting_bool(key: str, default: bool = False, branch=None) -> bool:
    """Read a boolean setting, coercing strings like "false"/"0" written by the UI."""
    raw = get_setting_value(key, branch=branch)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def set_setting_value(key: str, value, branch=None, actor=None) -> Setting:
    """Upsert a setting value (scalar stored in the JSON value)."""
    if branch is not None:
        row, _ = Setting.objects.update_or_create(
            key=key, branch=branch, defaults={"value": value}
        )
    else:
        row, _ = Setting.objects.update_or_create(
            key=key, branch=None, defaults={"value": value}
        )
    from apps.audit.services import log_action

    log_action(
        actor=actor,
        action="setting_updated",
        entity_type="Setting",
        entity_id=row.id,
        after={"key": key, "value": value, "branch": str(branch) if branch else None},
    )
    return row


def get_threshold(key: str, fallback: str) -> Decimal:
    """Read a decimal threshold setting with env fallback."""
    raw = get_setting_value(key)
    if raw is None:
        raw = fallback
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return Decimal(fallback)