"""Representative assignment services (effective-dated, one open row per pair)."""

from django.db import transaction
from django.utils import timezone

from apps.representatives.models import Representative, RepresentativeAssignment


@transaction.atomic
def assign(
    *,
    representative: Representative,
    entity_type: str,
    entity_id,
    effective_from=None,
    is_primary: bool = True,
):
    effective_from = effective_from or timezone.localdate()
    RepresentativeAssignment.objects.filter(
        representative=representative,
        entity_type=entity_type,
        entity_id=entity_id,
        effective_to__isnull=True,
    ).update(effective_to=effective_from)
    return RepresentativeAssignment.objects.create(
        representative=representative,
        entity_type=entity_type,
        entity_id=entity_id,
        effective_from=effective_from,
        is_primary=is_primary,
    )


@transaction.atomic
def unassign(*, representative: Representative, entity_type: str, entity_id, on_date=None):
    on_date = on_date or timezone.localdate()
    return RepresentativeAssignment.objects.filter(
        representative=representative,
        entity_type=entity_type,
        entity_id=entity_id,
        effective_to__isnull=True,
    ).update(effective_to=on_date)
