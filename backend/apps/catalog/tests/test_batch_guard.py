"""Guards that keep batch quantities ledger-controlled."""

import pytest

from apps.catalog.serializers import MedicineBatchSerializer

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("payload", [{"qty_on_hand": "99"}, {"qty_received_total": "99"}])
def test_batch_quantity_cannot_be_edited_directly(batch, payload):
    serializer = MedicineBatchSerializer(batch, data=payload, partial=True)
    assert not serializer.is_valid()
    assert "qty_on_hand" in serializer.errors


def test_batch_metadata_can_still_be_edited(batch):
    serializer = MedicineBatchSerializer(batch, data={"notes": "checked"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()
    assert updated.notes == "checked"
