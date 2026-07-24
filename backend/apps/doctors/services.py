"""Doctor mapping and visit services. Samples are issued from the promotional stock pool."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Medicine, MedicineBatch
from apps.common.exceptions import APIError
from apps.doctors.models import (
    Doctor,
    DoctorMedicine,
    DoctorVisit,
    DoctorVisitSample,
    VisitStatus,
)
from apps.inventory.models import EntryType, StockPool
from apps.inventory.services import MovementLine, post_transactions


@transaction.atomic
def open_medicine_mapping(*, doctor: Doctor, medicine: Medicine, priority: str = "", strength_note: str = ""):
    effective_from = timezone.localdate()
    DoctorMedicine.objects.filter(
        doctor=doctor, medicine=medicine, effective_to__isnull=True
    ).update(effective_to=effective_from)
    return DoctorMedicine.objects.create(
        doctor=doctor,
        medicine=medicine,
        priority=priority,
        strength_note=strength_note,
        effective_from=effective_from,
    )


@transaction.atomic
def end_medicine_mapping(*, mapping: DoctorMedicine):
    mapping.effective_to = timezone.localdate()
    mapping.save(update_fields=["effective_to", "updated_at"])
    return mapping


def _issue_sample(*, visit: DoctorVisit, medicine: Medicine, batch: MedicineBatch, qty: Decimal, actor):
    postings = post_transactions(
        branch=visit.branch,
        lines=[
            MovementLine(
                medicine=medicine,
                batch=batch,
                qty_delta=-Decimal(qty),
                unit_cost=batch.unit_cost,
                pool=StockPool.PROMO,
            )
        ],
        entry_type=EntryType.BONUS_ISSUE,
        source_type="DOCTOR_VISIT",
        source_id=visit.id,
        source_number=str(visit.id)[:8],
        business_date=visit.visited_at.date() if visit.visited_at else timezone.localdate(),
        actor=actor,
    )
    return postings[0]


@transaction.atomic
def complete_visit(
    *,
    visit: DoctorVisit,
    actor,
    visited_at=None,
    purpose: str = "",
    products_discussed: list | None = None,
    outcome: str = "",
    next_visit_date=None,
    notes: str = "",
    samples: list[dict] | None = None,
):
    visit = DoctorVisit.objects.select_for_update().select_related("branch", "doctor", "representative").get(id=visit.id)
    if visit.status == VisitStatus.COMPLETED:
        return visit
    if visit.status in (VisitStatus.MISSED, VisitStatus.CANCELLED):
        raise APIError("INVALID_STATUS_TRANSITION", "A cancelled or missed visit cannot be completed.")

    visit.visited_at = visited_at or timezone.now()
    if purpose:
        visit.purpose = purpose
    if products_discussed is not None:
        visit.products_discussed = [str(item) for item in products_discussed]
    if outcome:
        visit.outcome = outcome
    if next_visit_date:
        visit.next_visit_date = next_visit_date
    if notes:
        visit.notes = notes
    visit.status = VisitStatus.COMPLETED
    visit.save()

    for sample in samples or []:
        posting = _issue_sample(
            visit=visit,
            medicine=sample["medicine"],
            batch=sample["batch"],
            qty=Decimal(sample["qty"]),
            actor=actor,
        )
        DoctorVisitSample.objects.create(
            visit=visit,
            medicine=sample["medicine"],
            batch=sample["batch"],
            qty=Decimal(sample["qty"]),
            unit_cost=sample["batch"].unit_cost,
            inventory_transaction=posting,
        )
    return visit


@transaction.atomic
def mark_visit_missed(*, visit: DoctorVisit, reason: str = "", actor=None):
    visit = DoctorVisit.objects.select_for_update().get(id=visit.id)
    if visit.status != VisitStatus.PLANNED:
        raise APIError("INVALID_STATUS_TRANSITION", "Only planned visits can be marked missed.")
    visit.status = VisitStatus.MISSED
    visit.missed_reason = reason
    visit.save(update_fields=["status", "missed_reason", "updated_at"])
    return visit


def visit_coverage(user, date_from: date, date_to: date, filters: dict | None = None) -> dict:
    from django.db.models import Q

    queryset = DoctorVisit.objects.filter(
        Q(planned_date__range=(date_from, date_to))
        | Q(visited_at__date__range=(date_from, date_to))
    )
    filters = filters or {}
    if filters.get("branch"):
        queryset = queryset.filter(branch_id=filters["branch"])
    if filters.get("representative"):
        queryset = queryset.filter(representative_id=filters["representative"])

    per_rep: dict[str, dict] = {}
    ad_hoc_completed = 0
    for visit in queryset.select_related("representative"):
        row = per_rep.setdefault(
            str(visit.representative_id),
            {
                "representative": visit.representative_id,
                "representative_name": visit.representative.name,
                "planned": 0,
                "completed": 0,
                "missed": 0,
                "cancelled": 0,
            },
        )
        if visit.planned_date and date_from <= visit.planned_date <= date_to:
            row["planned"] += 1
        elif visit.status == VisitStatus.COMPLETED:
            ad_hoc_completed += 1
        if visit.status == VisitStatus.COMPLETED:
            row["completed"] += 1
        elif visit.status == VisitStatus.MISSED:
            row["missed"] += 1
        elif visit.status == VisitStatus.CANCELLED:
            row["cancelled"] += 1

    results = sorted(per_rep.values(), key=lambda row: row["representative_name"])
    for row in results:
        total = row["planned"]
        row["coverage_pct"] = round((row["completed"] / total) * 100, 1) if total else None
    return {"results": results, "ad_hoc_completed": ad_hoc_completed}
