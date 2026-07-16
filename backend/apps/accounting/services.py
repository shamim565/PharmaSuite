"""Financial account posting service — single choke-point for account movements."""

from decimal import Decimal
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from apps.accounting.models import FinancialAccount, FinancialTransaction
from apps.common.exceptions import APIError


def post_account_transaction(
    *,
    account: FinancialAccount,
    entry_type: str,
    amount_delta: Decimal,
    source_type: str = "",
    source_id: UUID | None = None,
    source_number: str = "",
    reference: str = "",
    business_date=None,
    actor=None,
    idempotency_key: str | None = None,
    reverses_entry: FinancialTransaction | None = None,
    transaction_group_id: UUID | None = None,
) -> FinancialTransaction:
    amount_delta = Decimal(amount_delta)
    if amount_delta == 0:
        raise APIError("INVALID_AMOUNT", "Amount must not be zero.")

    if idempotency_key:
        existing = FinancialTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    with transaction.atomic():
        locked = FinancialAccount.objects.select_for_update().get(id=account.id)
        new_balance = locked.balance_cache + amount_delta
        if new_balance < 0 and not locked.allow_negative:
            raise APIError(
                "INSUFFICIENT_FUNDS",
                f"Account {locked.name} has insufficient funds for this operation.",
                status_code=409,
            )

        posting = FinancialTransaction.objects.create(
            account=locked,
            entry_type=entry_type,
            amount_delta=amount_delta,
            reference=reference,
            source_type=source_type,
            source_id=source_id,
            source_number=source_number,
            transaction_group_id=transaction_group_id or uuid4(),
            reverses_entry=reverses_entry,
            idempotency_key=idempotency_key,
            business_date=business_date or timezone.localdate(),
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        locked.balance_cache = new_balance
        locked.save(update_fields=["balance_cache", "updated_at"])

    return posting


def account_ledger_balance(account: FinancialAccount) -> Decimal:
    from django.db.models import Sum

    total = FinancialTransaction.objects.filter(account=account).aggregate(total=Sum("amount_delta"))[
        "total"
    ]
    return total or Decimal("0")
