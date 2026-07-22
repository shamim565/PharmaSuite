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


# --------------------------------------------------------------------------- expenses

def _expense_threshold() -> Decimal:
    from django.conf import settings

    return Decimal(str(getattr(settings, "EXPENSE_APPROVAL_THRESHOLD", "5000")))


def _post_expense(expense, actor) -> None:
    from apps.common.models import DocumentType
    from apps.common.numbering import allocate_number

    expense.number = expense.number or allocate_number(
        branch=expense.branch, doc_type=DocumentType.EXPENSE, business_date=expense.business_date
    )
    expense.status = "POSTED"
    expense.posted_at = timezone.now()
    expense.save(update_fields=["number", "status", "posted_at", "updated_at"])
    post_account_transaction(
        account=expense.account,
        entry_type="EXPENSE",
        amount_delta=-expense.amount,
        source_type="EXPENSE",
        source_id=expense.id,
        source_number=expense.number,
        reference=expense.reference,
        business_date=expense.business_date,
        actor=actor,
    )


@transaction.atomic
def create_expense(
    *,
    branch,
    category,
    amount: Decimal,
    account,
    business_date=None,
    payee: str = "",
    reference: str = "",
    note: str = "",
    actor=None,
    idempotency_key: str | None = None,
):
    from apps.accounting.models import Expense

    if idempotency_key:
        existing = Expense.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Expense amount must be positive.")

    expense = Expense.objects.create(
        branch=branch,
        business_date=business_date or timezone.localdate(),
        category=category,
        amount=amount,
        account=account,
        payee=payee,
        reference=reference,
        note=note,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
        idempotency_key=idempotency_key,
    )
    if amount > _expense_threshold():
        expense.status = "PENDING_APPROVAL"
        expense.save(update_fields=["status", "updated_at"])
    else:
        _post_expense(expense, actor)
    return expense


@transaction.atomic
def approve_expense(*, expense, actor):
    from apps.accounting.models import Expense

    expense = Expense.objects.select_for_update().get(id=expense.id)
    if expense.status != "PENDING_APPROVAL":
        raise APIError("INVALID_STATUS_TRANSITION", "Only pending expenses can be approved.")
    if actor.id == expense.requested_by_id:
        raise APIError(
            "SELF_APPROVAL_NOT_ALLOWED",
            "The requester cannot approve their own expense (dual control).",
            status_code=403,
        )
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.save(update_fields=["approved_by", "approved_at", "updated_at"])
    _post_expense(expense, actor)
    return expense


@transaction.atomic
def reject_expense(*, expense, actor, reason: str = ""):
    from apps.accounting.models import Expense

    expense = Expense.objects.select_for_update().get(id=expense.id)
    if expense.status != "PENDING_APPROVAL":
        raise APIError("INVALID_STATUS_TRANSITION", "Only pending expenses can be rejected.")
    if actor.id == expense.requested_by_id:
        raise APIError(
            "SELF_APPROVAL_NOT_ALLOWED",
            "The requester cannot reject their own expense (dual control).",
            status_code=403,
        )
    expense.status = "REJECTED"
    expense.rejection_reason = reason
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.save(update_fields=["status", "rejection_reason", "approved_by", "approved_at", "updated_at"])
    return expense


@transaction.atomic
def reverse_expense(*, expense, actor, reason: str = ""):
    from apps.accounting.models import Expense

    expense = Expense.objects.select_for_update().select_related("account", "branch").get(id=expense.id)
    if expense.status != "POSTED":
        raise APIError("INVALID_STATUS_TRANSITION", "Only posted expenses can be reversed.")
    original = FinancialTransaction.objects.filter(source_type="EXPENSE", source_id=expense.id).first()
    post_account_transaction(
        account=expense.account,
        entry_type="EXPENSE_REVERSAL",
        amount_delta=expense.amount,
        source_type="EXPENSE",
        source_id=expense.id,
        source_number=expense.number or "",
        reference=expense.reference,
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original,
    )
    expense.status = "REVERSED"
    expense.note = (expense.note + f"\nReversed: {reason}").strip()
    expense.save(update_fields=["status", "note", "updated_at"])
    return expense


# --------------------------------------------------------------------------- income

@transaction.atomic
def create_income(
    *,
    branch,
    category,
    amount: Decimal,
    account,
    business_date=None,
    source: str = "",
    reference: str = "",
    note: str = "",
    actor=None,
    idempotency_key: str | None = None,
):
    from apps.accounting.models import Income
    from apps.common.models import DocumentType
    from apps.common.numbering import allocate_number

    if idempotency_key:
        existing = Income.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Income amount must be positive.")

    income = Income.objects.create(
        branch=branch,
        business_date=business_date or timezone.localdate(),
        category=category,
        amount=amount,
        account=account,
        source=source,
        reference=reference,
        note=note,
        posted_by=actor if getattr(actor, "is_authenticated", False) else None,
        idempotency_key=idempotency_key,
    )
    income.number = allocate_number(
        branch=branch, doc_type=DocumentType.INCOME, business_date=income.business_date
    )
    income.posted_at = timezone.now()
    income.save(update_fields=["number", "posted_at", "updated_at"])
    post_account_transaction(
        account=account,
        entry_type="INCOME",
        amount_delta=amount,
        source_type="INCOME",
        source_id=income.id,
        source_number=income.number,
        reference=reference,
        business_date=income.business_date,
        actor=actor,
    )
    return income


@transaction.atomic
def reverse_income(*, income, actor, reason: str = ""):
    from apps.accounting.models import Income

    income = Income.objects.select_for_update().select_related("account", "branch").get(id=income.id)
    if income.status != "POSTED":
        raise APIError("INVALID_STATUS_TRANSITION", "Only posted income can be reversed.")
    original = FinancialTransaction.objects.filter(source_type="INCOME", source_id=income.id).first()
    post_account_transaction(
        account=income.account,
        entry_type="INCOME_REVERSAL",
        amount_delta=-income.amount,
        source_type="INCOME",
        source_id=income.id,
        source_number=income.number or "",
        reference=income.reference,
        business_date=timezone.localdate(),
        actor=actor,
        reverses_entry=original,
    )
    income.status = "REVERSED"
    income.note = (income.note + f"\nReversed: {reason}").strip()
    income.save(update_fields=["status", "note", "updated_at"])
    return income


# --------------------------------------------------------------------------- account operations

@transaction.atomic
def deposit_to_account(*, account, amount: Decimal, reference: str = "", actor=None):
    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Deposit amount must be positive.")
    return post_account_transaction(
        account=account,
        entry_type="DEPOSIT",
        amount_delta=amount,
        source_type="ACCOUNT_DEPOSIT",
        reference=reference,
        actor=actor,
    )


@transaction.atomic
def withdraw_from_account(*, account, amount: Decimal, reference: str = "", actor=None):
    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Withdrawal amount must be positive.")
    return post_account_transaction(
        account=account,
        entry_type="WITHDRAWAL",
        amount_delta=-amount,
        source_type="ACCOUNT_WITHDRAWAL",
        reference=reference,
        actor=actor,
    )


@transaction.atomic
def transfer_between_accounts(*, from_account, to_account, amount: Decimal, reference: str = "", actor=None):
    from uuid import uuid4

    if from_account.id == to_account.id:
        raise APIError("INVALID_TRANSFER", "Source and destination accounts must differ.")
    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise APIError("INVALID_AMOUNT", "Transfer amount must be positive.")

    group_id = uuid4()
    out_txn = post_account_transaction(
        account=from_account,
        entry_type="TRANSFER_OUT",
        amount_delta=-amount,
        source_type="ACCOUNT_TRANSFER",
        reference=reference,
        actor=actor,
        transaction_group_id=group_id,
    )
    in_txn = post_account_transaction(
        account=to_account,
        entry_type="TRANSFER_IN",
        amount_delta=amount,
        source_type="ACCOUNT_TRANSFER",
        reference=reference,
        actor=actor,
        transaction_group_id=group_id,
    )
    return group_id, out_txn, in_txn
