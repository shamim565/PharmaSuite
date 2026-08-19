"""Visit/sample integrity: branch ownership, lifecycle lock, scope, cancel."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope, UserBranch
from apps.accounts.tests.helpers import grant_role
from apps.common.exceptions import APIError
from apps.doctors.models import Doctor, DoctorVisit, VisitStatus
from apps.doctors.services import (
    cancel_visit,
    complete_visit,
    mark_visit_missed,
    reverse_visit_samples,
)
from apps.inventory.models import EntryType, InventoryTransaction, StockBalance, StockPool
from apps.inventory.services import MovementLine, post_transactions
from apps.representatives.models import Representative

pytestmark = pytest.mark.django_db


@pytest.fixture
def doctor(db):
    return Doctor.objects.create(code="DOC-1", name="Dr House")


@pytest.fixture
def representative(db, branch):
    return Representative.objects.create(code="REP-1", name="Rep One", branch=branch)


def _visit(branch, doctor, representative, planned_date=None):
    return DoctorVisit.objects.create(
        doctor=doctor,
        representative=representative,
        branch=branch,
        planned_date=planned_date or timezone.localdate(),
    )


def _promo_stock(branch, batch, qty, actor):
    return post_transactions(
        branch=branch,
        lines=[
            MovementLine(
                medicine=batch.medicine,
                batch=batch,
                qty_delta=Decimal(str(qty)),
                pool=StockPool.PROMO,
            )
        ],
        entry_type=EntryType.BONUS,
        business_date=timezone.localdate(),
        actor=actor,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_sample_batch_must_belong_to_visit_branch(
    branch, second_branch, doctor, representative, medicine, make_batch, actor
):
    visit = _visit(branch, doctor, representative)
    foreign_batch = make_batch(batch_number="FOREIGN")
    foreign_batch.branch = second_branch
    foreign_batch.save(update_fields=["branch", "updated_at"])

    with pytest.raises(APIError) as exc:
        complete_visit(
            visit=visit,
            actor=actor,
            samples=[{"medicine": medicine, "batch": foreign_batch, "qty": Decimal("1")}],
        )
    assert exc.value.code == "INVALID_BATCH"

    visit.refresh_from_db()
    assert visit.status == VisitStatus.PLANNED
    assert InventoryTransaction.objects.count() == 0


def test_sample_issued_from_promo_pool(
    branch, doctor, representative, medicine, make_batch, actor
):
    visit = _visit(branch, doctor, representative)
    batch = make_batch()
    _promo_stock(branch, batch, "5", actor)

    completed = complete_visit(
        visit=visit,
        actor=actor,
        samples=[{"medicine": medicine, "batch": batch, "qty": Decimal("2")}],
    )

    assert completed.status == VisitStatus.COMPLETED
    assert StockBalance.objects.get(batch=batch).qty_promo == Decimal("3")
    sample = completed.samples.get()
    assert sample.medicine_id == medicine.id
    assert sample.inventory_transaction is not None
    assert sample.inventory_transaction.entry_type == EntryType.BONUS_ISSUE


def test_sample_requires_promo_stock(
    branch, doctor, representative, medicine, make_batch, actor
):
    visit = _visit(branch, doctor, representative)
    batch = make_batch()

    with pytest.raises(APIError) as exc:
        complete_visit(
            visit=visit,
            actor=actor,
            samples=[{"medicine": medicine, "batch": batch, "qty": Decimal("1")}],
        )
    assert exc.value.code == "INSUFFICIENT_STOCK"
    visit.refresh_from_db()
    assert visit.status == VisitStatus.PLANNED


def test_visit_status_is_read_only(branch, doctor, representative, actor):
    grant_role(actor, ["VISIT_MANAGE"], branch_scope=BranchScope.ALL)
    visit = _visit(branch, doctor, representative)

    response = _client(actor).patch(
        f"/api/v1/doctor-visits/{visit.id}/", {"status": "COMPLETED"}, format="json"
    )

    assert response.status_code == 200
    visit.refresh_from_db()
    assert visit.status == VisitStatus.PLANNED


def test_completed_visit_cannot_be_edited(branch, doctor, representative, actor):
    grant_role(actor, ["VISIT_MANAGE"], branch_scope=BranchScope.ALL)
    visit = _visit(branch, doctor, representative)
    complete_visit(visit=visit, actor=actor, outcome="PRESCRIBING")

    response = _client(actor).patch(
        f"/api/v1/doctor-visits/{visit.id}/", {"purpose": "changed"}, format="json"
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_STATUS_TRANSITION"


def test_cancel_planned_visit(branch, doctor, representative, actor):
    visit = _visit(branch, doctor, representative)

    cancelled = cancel_visit(visit=visit, actor=actor, reason="doctor unavailable")
    cancelled.refresh_from_db()
    assert cancelled.status == VisitStatus.CANCELLED
    assert cancelled.cancel_reason == "doctor unavailable"

    with pytest.raises(APIError):
        cancel_visit(visit=cancelled, actor=actor)


def test_cannot_cancel_completed_visit(branch, doctor, representative, actor):
    visit = _visit(branch, doctor, representative)
    complete_visit(visit=visit, actor=actor)

    with pytest.raises(APIError) as exc:
        cancel_visit(visit=visit, actor=actor)
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


def test_reverse_visit_samples_restocks_promo(
    branch, doctor, representative, medicine, make_batch, actor
):
    visit = _visit(branch, doctor, representative)
    batch = make_batch()
    _promo_stock(branch, batch, "5", actor)
    complete_visit(
        visit=visit,
        actor=actor,
        samples=[{"medicine": medicine, "batch": batch, "qty": Decimal("2")}],
    )
    assert StockBalance.objects.get(batch=batch).qty_promo == Decimal("3")

    reversed_visit = reverse_visit_samples(visit=visit, actor=actor, reason="wrong batch")
    assert StockBalance.objects.get(batch=batch).qty_promo == Decimal("5")
    assert all(sample.reversed for sample in reversed_visit.samples.all())
    assert "wrong batch" in reversed_visit.notes

    with pytest.raises(APIError) as exc:
        reverse_visit_samples(visit=reversed_visit, actor=actor)
    assert exc.value.code == "NOTHING_TO_REVERSE"


def test_reverse_samples_requires_completed_visit(branch, doctor, representative, actor):
    visit = _visit(branch, doctor, representative)

    with pytest.raises(APIError) as exc:
        reverse_visit_samples(visit=visit, actor=actor)
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


def test_visit_coverage_report(branch, doctor, representative, actor):
    grant_role(actor, ["VISIT_VIEW"], branch_scope=BranchScope.ALL)
    today = timezone.localdate()
    done = _visit(branch, doctor, representative, planned_date=today)
    complete_visit(visit=done, actor=actor)
    _visit(branch, doctor, representative, planned_date=today)
    missed = _visit(branch, doctor, representative, planned_date=today)
    mark_visit_missed(visit=missed, actor=actor, reason="no show")

    response = _client(actor).get(
        f"/api/v1/doctors/reports/visit-coverage/?date_from={today}&date_to={today}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["planned"] == 3
    assert row["completed"] == 1
    assert row["missed"] == 1
    assert row["cancelled"] == 0
    assert row["coverage_pct"] == 33.3


def test_visit_create_rejects_out_of_scope_branch(
    branch, second_branch, doctor, representative, actor
):
    grant_role(actor, ["VISIT_MANAGE"], branch_scope=BranchScope.ASSIGNED)
    UserBranch.objects.create(user=actor, branch=branch)
    actor._permission_cache = None

    response = _client(actor).post(
        "/api/v1/doctor-visits/",
        {
            "doctor": str(doctor.id),
            "representative": str(representative.id),
            "branch": str(second_branch.id),
            "planned_date": timezone.localdate().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "BRANCH_SCOPE_EXCEEDED"
    assert DoctorVisit.objects.count() == 0
