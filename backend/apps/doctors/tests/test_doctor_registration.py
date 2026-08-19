"""Doctor registration numbers are uniquely enforced case-insensitively."""

import pytest
from django.db import IntegrityError, transaction

from apps.doctors.models import Doctor

pytestmark = pytest.mark.django_db


def test_registration_number_case_insensitive_unique():
    Doctor.objects.create(code="DOC-A", name="Dr A", registration_no="REG-ABC")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Doctor.objects.create(code="DOC-B", name="Dr B", registration_no="reg-abc")


def test_multiple_doctors_without_registration_number():
    Doctor.objects.create(code="DOC-C", name="Dr C")
    Doctor.objects.create(code="DOC-D", name="Dr D")

    assert Doctor.objects.filter(registration_no__isnull=True).count() == 2
