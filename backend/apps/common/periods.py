"""Fiscal period model helpers and posting lock enforcement (July–June FY)."""

from datetime import date, timedelta

from django.utils import timezone

from apps.common.exceptions import APIError
from apps.common.models import FiscalPeriod, FiscalPeriodStatus


def fiscal_year_for(business_date: date | None = None) -> int:
    value = business_date or timezone.localdate()
    return value.year if value.month >= 7 else value.year - 1


def fiscal_month_index(business_date: date | None = None) -> int:
    """1 = July … 12 = June."""
    value = business_date or timezone.localdate()
    return value.month - 6 if value.month >= 7 else value.month + 6


def month_bounds_fixed(fiscal_year: int, period_month: int) -> tuple[date, date]:
    """Start/end dates for fiscal month 1..12 (1=July of fiscal_year)."""
    start_month = 6 + period_month  # July = month 7
    year = fiscal_year
    if start_month > 12:
        start_month -= 12
        year += 1
    start = date(year, start_month, 1)
    if start_month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, start_month + 1, 1)
    return start, end - timedelta(days=1)


def get_or_create_period(business_date: date | None = None) -> FiscalPeriod:
    value = business_date or timezone.localdate()
    fiscal_year = fiscal_year_for(value)
    period_month = fiscal_month_index(value)
    period, _ = FiscalPeriod.objects.get_or_create(
        fiscal_year=fiscal_year,
        period_month=period_month,
        defaults={
            "start_date": month_bounds_fixed(fiscal_year, period_month)[0],
            "end_date": month_bounds_fixed(fiscal_year, period_month)[1],
        },
    )
    return period


def ensure_fiscal_periods(fiscal_year: int | None = None) -> int:
    """Create the 12 fiscal months of a year (and the next) if missing."""
    fiscal_year = fiscal_year or fiscal_year_for()
    created = 0
    for year in (fiscal_year, fiscal_year + 1):
        for period_month in range(1, 13):
            _, was_created = FiscalPeriod.objects.get_or_create(
                fiscal_year=year,
                period_month=period_month,
                defaults={
                    "start_date": month_bounds_fixed(year, period_month)[0],
                    "end_date": month_bounds_fixed(year, period_month)[1],
                },
            )
            created += int(was_created)
    return created


def actor_has_period_override(actor) -> bool:
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and (actor.is_superuser or "PERIOD_OVERRIDE" in actor.effective_permission_codes)
    )


def ensure_period_open(business_date: date | None = None, actor=None) -> FiscalPeriod:
    """Raise PERIOD_LOCKED when the fiscal month is locked (unless override)."""
    period = get_or_create_period(business_date)
    if period.status == FiscalPeriodStatus.LOCKED and not actor_has_period_override(actor):
        raise APIError(
            "PERIOD_LOCKED",
            f"Fiscal period {period.start_date} to {period.end_date} is locked. "
            "Ask the owner to unlock it or use a period override.",
            status_code=409,
        )
    return period


def lock_period(*, period: FiscalPeriod, actor, reason: str = "", checklist: dict | None = None, idempotency_key: str | None = None) -> FiscalPeriod:
    period.status = FiscalPeriodStatus.LOCKED
    period.locked_by = actor
    period.locked_at = timezone.now()
    period.lock_reason = reason
    period.unlock_by = None
    period.unlock_at = None
    period.unlock_reason = ""
    period.idempotency_key = idempotency_key or period.idempotency_key
    period.save(update_fields=["status", "locked_by", "locked_at", "lock_reason", "unlock_by", "unlock_at", "unlock_reason", "idempotency_key", "updated_at"])
    return period


def unlock_period(*, period: FiscalPeriod, actor, reason: str = "", idempotency_key: str | None = None) -> FiscalPeriod:
    if not actor_has_period_override(actor):
        raise APIError(
            "PERMISSION_DENIED", "Only the owner may reopen a locked fiscal period.", status_code=403
        )
    period.status = FiscalPeriodStatus.OPEN
    period.unlock_by = actor
    period.unlock_at = timezone.now()
    period.unlock_reason = reason
    period.idempotency_key = idempotency_key or period.idempotency_key
    period.save(update_fields=["status", "unlock_by", "unlock_at", "unlock_reason", "idempotency_key", "updated_at"])
    return period