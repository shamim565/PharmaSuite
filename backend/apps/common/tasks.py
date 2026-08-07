import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.common.tasks.heartbeat")
def heartbeat() -> dict:
    """Periodic liveness task; also used to smoke-test workers."""
    timestamp = timezone.now().isoformat()
    logger.info("celery heartbeat at %s", timestamp)
    return {"status": "ok", "timestamp": timestamp}


@shared_task(name="apps.common.tasks.daily_stock_alerts")
def daily_stock_alerts() -> dict:
    """Low-stock, near-expiry and expired summaries for stock roles."""
    from apps.common.notifications import notify_users, role_users
    from apps.inventory.models import StockBalance

    today = timezone.localdate()
    users = role_users("stock")
    created = 0

    balances = StockBalance.objects.select_related("medicine", "batch")
    low = {}
    near = []
    expired = []
    for balance in balances:
        key = str(balance.medicine_id)
        low.setdefault(key, {"qty": 0, "reorder": 0, "name": balance.medicine.name})
        low[key]["qty"] += balance.qty_on_hand
        if balance.medicine.reorder_level > 0:
            low[key]["reorder"] = balance.medicine.reorder_level
        if balance.batch.expiry_date:
            days = (balance.batch.expiry_date - today).days
            if 0 <= days <= 90:
                near.append((balance.medicine.name, balance.batch.batch_number, days))
            if days < 0:
                expired.append((balance.medicine.name, balance.batch.batch_number, -days))

    low_rows = [row for row in low.values() if row["reorder"] > 0 and row["qty"] <= row["reorder"]]
    low_text = ", ".join(f"{row['name']} ({row['qty']}/{row['reorder']})" for row in low_rows[:8])
    if low_rows:
        created += notify_users(
            users,
            "LOW_STOCK",
            f"Low stock: {len(low_rows)} item(s)",
            low_text or "Check the inventory page.",
            "/inventory",
            severity="WARNING",
            category="STOCK",
        )
    if near:
        created += notify_users(
            users,
            "NEAR_EXPIRY",
            f"Near expiry: {len(near)} batch(es) within 90 days",
            "; ".join(f"{name} {batch} ({days}d)" for name, batch, days in near[:8]),
            "/inventory",
            severity="WARNING",
            category="EXPIRY",
        )
    if expired:
        created += notify_users(
            users,
            "EXPIRED",
            f"Expired stock: {len(expired)} batch(es)",
            "; ".join(f"{name} {batch} ({days}d)" for name, batch, days in expired[:8]),
            "/inventory",
            severity="CRITICAL",
            category="EXPIRY",
        )
    return {"created": created, "low": len(low_rows), "near": len(near), "expired": len(expired)}


@shared_task(name="apps.common.tasks.daily_due_alerts")
def daily_due_alerts() -> dict:
    """Overdue dues and pending approvals digests for finance roles."""
    from apps.accounting.models import Expense
    from apps.common.notifications import notify_users, role_users
    from apps.inventory.models import StockAdjustment
    from apps.sales.models import SalesInvoice

    today = timezone.localdate()
    users = role_users("finance")
    created = 0

    from django.db.models import F

    overdue_invoices = SalesInvoice.objects.filter(
        lifecycle="CONFIRMED", due_date__lt=today, paid_total__lt=F("grand_total")
    )
    overdue_count = overdue_invoices.count()
    if overdue_count:
        overdue_value = sum(
            (inv.grand_total - inv.paid_total for inv in overdue_invoices[:200]), 0
        )
        created += notify_users(
            users,
            "OVERDUE_DUES",
            f"{overdue_count} invoice(s) overdue",
            f"Total overdue: {overdue_value:.2f}",
            "/dues",
            severity="WARNING",
            category="DUES",
        )

    pending_expenses = Expense.objects.filter(status="PENDING_APPROVAL").count()
    pending_adjustments = StockAdjustment.objects.filter(status="PENDING_APPROVAL").count()
    if pending_expenses or pending_adjustments:
        created += notify_users(
            users,
            "PENDING_APPROVALS",
            "Pending approvals",
            f"{pending_expenses} expense(s), {pending_adjustments} adjustment(s)",
            "/expenses",
            severity="WARNING",
            category="APPROVALS",
        )
    return {"created": created, "overdue": overdue_count, "pending": pending_expenses + pending_adjustments}


@shared_task(name="apps.common.tasks.visit_reminders")
def visit_reminders() -> dict:
    """Remind MRs about visits planned for tomorrow."""
    from datetime import timedelta

    from apps.common.notifications import notify_users
    from apps.doctors.models import DoctorVisit

    tomorrow = timezone.localdate() + timedelta(days=1)
    visits = DoctorVisit.objects.filter(status="PLANNED", planned_date=tomorrow).select_related(
        "representative", "doctor"
    )
    by_rep: dict[str, list] = {}
    for visit in visits:
        if visit.representative.user_id:
            by_rep.setdefault(str(visit.representative.user_id), []).append(visit.doctor.name)

    created = 0
    for user_id, doctors in by_rep.items():
        from apps.accounts.models import User

        user = User.objects.filter(id=user_id, status="ACTIVE").first()
        if user:
            created += notify_users(
                [user],
                "VISIT_REMINDER",
                f"{len(doctors)} visit(s) planned tomorrow",
                ", ".join(doctors[:8]),
                "/doctors",
                category="VISITS",
            )
    return {"created": created, "reps_notified": len(by_rep)}