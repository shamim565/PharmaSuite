"""Tests for warehouse bin/rack locations."""

import pytest
from django.db import IntegrityError

from apps.inventory.models import WarehouseLocation

pytestmark = pytest.mark.django_db


def test_location_label_and_uniqueness(branch):
    location = WarehouseLocation.objects.create(
        branch=branch, zone="A", rack="R1", bin="B3"
    )
    assert location.label == "A-R1-B3"

    with pytest.raises(IntegrityError):
        WarehouseLocation.objects.create(branch=branch, zone="A", rack="R1", bin="B3")


def test_location_without_zone_uses_bin(branch):
    location = WarehouseLocation.objects.create(branch=branch, bin="B9")
    assert location.label == "B9"


def test_batch_location_can_be_assigned(branch, medicine, make_batch):
    batch = make_batch(batch_number="LOC-1")
    assert batch.location == ""

    batch.location = "A-R1-B3"
    batch.save(update_fields=["location", "updated_at"])
    batch.refresh_from_db()
    assert batch.location == "A-R1-B3"
