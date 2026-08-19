"""Doctor chambers enforce the view/manage split (regression for unmapped actions)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.helpers import grant_role
from apps.doctors.models import Doctor, DoctorChamber

pytestmark = pytest.mark.django_db


@pytest.fixture
def doctor(db):
    return Doctor.objects.create(code="DOC-1", name="Dr House")


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_chambers_read_requires_doctor_view(actor, doctor):
    grant_role(actor, ["USER_VIEW"])

    response = _client(actor).get(f"/api/v1/doctors/{doctor.id}/chambers/")

    assert response.status_code == 403


def test_chambers_read_allowed_for_viewer(actor, doctor):
    grant_role(actor, ["DOCTOR_VIEW"])

    response = _client(actor).get(f"/api/v1/doctors/{doctor.id}/chambers/")

    assert response.status_code == 200


def test_chambers_create_requires_doctor_manage(actor, doctor):
    grant_role(actor, ["DOCTOR_VIEW"])

    response = _client(actor).post(
        f"/api/v1/doctors/{doctor.id}/chambers/", {"name": "Chamber 1"}
    )

    assert response.status_code == 403
    assert DoctorChamber.objects.count() == 0


def test_chambers_create_allowed_for_manager(actor, doctor):
    grant_role(actor, ["DOCTOR_VIEW", "DOCTOR_MANAGE"])

    response = _client(actor).post(
        f"/api/v1/doctors/{doctor.id}/chambers/",
        {"name": "Chamber 1", "doctor": str(doctor.id)},
        format="json",
    )

    assert response.status_code == 201, response.json()
    assert DoctorChamber.objects.count() == 1


def test_chamber_delete_requires_doctor_manage(actor, doctor):
    grant_role(actor, ["DOCTOR_VIEW"])
    chamber = DoctorChamber.objects.create(doctor=doctor, name="Old")

    response = _client(actor).delete(f"/api/v1/doctors/{doctor.id}/chambers/{chamber.id}/")

    assert response.status_code == 403
    assert DoctorChamber.objects.count() == 1
