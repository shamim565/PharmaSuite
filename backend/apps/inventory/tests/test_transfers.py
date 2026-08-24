"""Inter-branch stock transfer tests."""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope
from apps.accounts.tests.helpers import grant_role
from apps.catalog.models import MedicineBatch
from apps.common.exceptions import APIError
from apps.inventory.models import EntryType, InventoryTransaction, StockBalance, TransferStatus
from apps.inventory.services import confirm_stock_transfer, create_stock_transfer

pytestmark = pytest.mark.django_db


def _create(branch, second_branch, medicine, batch, qty, actor):
    return create_stock_transfer(
        from_branch=branch,
        to_branch=second_branch,
        business_date=timezone.localdate(),
        items_data=[{"medicine": medicine, "batch": batch, "qty": Decimal(qty)}],
        actor=actor,
    )


def test_confirm_moves_stock_across_branches(
    branch, second_branch, medicine, make_batch, stock_in, actor
):
    batch = make_batch(batch_number="B1")
    stock_in(batch, "10")

    transfer = _create(branch, second_branch, medicine, batch, "4", actor)
    confirmed = confirm_stock_transfer(transfer=transfer, actor=actor)

    assert confirmed.status == TransferStatus.CONFIRMED
    assert confirmed.number and confirmed.number.startswith("TRF-")

    assert StockBalance.objects.get(branch=branch, batch=batch).qty_on_hand == Decimal("6")

    target_batch = MedicineBatch.objects.get(branch=second_branch, batch_number="B1")
    assert target_batch.medicine_id == medicine.id
    assert target_batch.unit_cost == batch.unit_cost
    assert StockBalance.objects.get(branch=second_branch, batch=target_batch).qty_on_hand == Decimal("4")

    rows = InventoryTransaction.objects.filter(entry_type=EntryType.TRANSFER)
    assert rows.count() == 2
    assert {row.qty_delta for row in rows} == {Decimal("-4"), Decimal("4")}


def test_same_branch_transfer_rejected(branch, medicine, make_batch, stock_in, actor):
    batch = make_batch()
    stock_in(batch, "10")

    with pytest.raises(APIError) as exc:
        create_stock_transfer(
            from_branch=branch,
            to_branch=branch,
            items_data=[{"medicine": medicine, "batch": batch, "qty": Decimal("1")}],
            actor=actor,
        )
    assert exc.value.code == "SAME_BRANCH"


def test_source_batch_must_belong_to_source_branch(
    branch, second_branch, medicine, make_batch, actor
):
    foreign_batch = make_batch(batch_number="FOREIGN")
    foreign_batch.branch = second_branch
    foreign_batch.save(update_fields=["branch", "updated_at"])

    with pytest.raises(APIError) as exc:
        create_stock_transfer(
            from_branch=branch,
            to_branch=second_branch,
            items_data=[{"medicine": medicine, "batch": foreign_batch, "qty": Decimal("1")}],
            actor=actor,
        )
    assert exc.value.code == "INVALID_BATCH"


def test_insufficient_stock_rolls_back(
    branch, second_branch, medicine, make_batch, stock_in, actor
):
    batch = make_batch()
    stock_in(batch, "2")
    transfer = _create(branch, second_branch, medicine, batch, "5", actor)

    with pytest.raises(APIError) as exc:
        confirm_stock_transfer(transfer=transfer, actor=actor)
    assert exc.value.code == "INSUFFICIENT_STOCK"

    transfer.refresh_from_db()
    assert transfer.status == TransferStatus.DRAFT
    assert transfer.number is None
    assert StockBalance.objects.get(branch=branch, batch=batch).qty_on_hand == Decimal("2")
    assert not MedicineBatch.objects.filter(branch=second_branch).exists()
    assert InventoryTransaction.objects.count() == 1  # only the stock-in
    assert MedicineBatch.objects.filter(branch=second_branch, batch_number="B1").count() == 0


def test_confirm_is_idempotent(branch, second_branch, medicine, make_batch, stock_in, actor):
    batch = make_batch()
    stock_in(batch, "10")
    transfer = _create(branch, second_branch, medicine, batch, "3", actor)

    first = confirm_stock_transfer(transfer=transfer, actor=actor)
    second = confirm_stock_transfer(transfer=transfer, actor=actor)

    assert first.number == second.number
    assert InventoryTransaction.objects.filter(entry_type=EntryType.TRANSFER).count() == 2


def test_transfer_into_existing_target_batch(
    branch, second_branch, medicine, make_batch, stock_in, actor
):
    source_batch = make_batch(batch_number="SHARED")
    stock_in(source_batch, "10")
    target_batch = MedicineBatch.objects.create(
        branch=second_branch,
        medicine=medicine,
        batch_number="SHARED",
        expiry_date=source_batch.expiry_date,
        unit_cost=Decimal("9.0000"),
    )

    transfer = _create(branch, second_branch, medicine, source_batch, "4", actor)
    confirm_stock_transfer(transfer=transfer, actor=actor)

    assert MedicineBatch.objects.filter(branch=second_branch, batch_number="SHARED").count() == 1
    assert StockBalance.objects.get(branch=second_branch, batch=target_batch).qty_on_hand == Decimal("4")


def test_api_requires_transfer_permission(
    branch, second_branch, medicine, make_batch, stock_in, actor
):
    grant_role(actor, ["STOCK_VIEW"], branch_scope=BranchScope.ALL)
    batch = make_batch()
    stock_in(batch, "10")
    client = APIClient()
    client.force_authenticate(actor)
    payload = {
        "from_branch": str(branch.id),
        "to_branch": str(second_branch.id),
        "items": [{"medicine": str(medicine.id), "batch": str(batch.id), "qty": "2"}],
    }

    denied = client.post("/api/v1/inventory/transfers/", payload, format="json")
    assert denied.status_code == 403

    grant_role(actor, ["STOCK_TRANSFER"], branch_scope=BranchScope.ALL)
    client = APIClient()
    client.force_authenticate(actor)
    created = client.post("/api/v1/inventory/transfers/", payload, format="json")
    assert created.status_code == 201, created.json()

    confirmed = client.post(
        f"/api/v1/inventory/transfers/{created.json()['id']}/confirm/", {}, format="json"
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"
