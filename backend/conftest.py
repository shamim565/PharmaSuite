"""Shared pytest fixtures for the ERP backend test suite."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.branches.models import Branch
from apps.catalog.models import Medicine, MedicineBatch, Unit
from apps.inventory.models import EntryType
from apps.inventory.services import MovementLine, post_transactions
from apps.sales.models import Customer
from apps.suppliers.models import Supplier


@pytest.fixture
def branch(db):
    return Branch.objects.create(code="MAIN", name="Main Branch")


@pytest.fixture
def second_branch(db):
    return Branch.objects.create(code="BR02", name="Second Branch")


@pytest.fixture
def actor(db):
    return User.objects.create_user(
        mobile="01700000001", password="Test@1234", full_name="Test User"
    )


@pytest.fixture
def approver(db):
    return User.objects.create_user(
        mobile="01700000002", password="Test@1234", full_name="Approver User"
    )


@pytest.fixture
def unit(db):
    return Unit.objects.create(name="Piece", symbol="pc")


@pytest.fixture
def medicine(db, unit):
    return Medicine.objects.create(
        code="MED-001",
        name="Paracetamol 500mg",
        base_unit=unit,
        purchase_price=Decimal("10.00"),
        selling_price=Decimal("12.00"),
        mrp=Decimal("13.00"),
        reorder_level=Decimal("5.000"),
    )


@pytest.fixture
def make_batch(branch, medicine):
    def _make(batch_number="B1", days_to_expiry=365, unit_cost="10.0000"):
        return MedicineBatch.objects.create(
            branch=branch,
            medicine=medicine,
            batch_number=batch_number,
            expiry_date=timezone.localdate() + timedelta(days=days_to_expiry),
            unit_cost=Decimal(unit_cost),
        )

    return _make


@pytest.fixture
def batch(make_batch):
    return make_batch()


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(code="SUP-001", name="Acme Pharma", credit_days=0)


@pytest.fixture
def customer(db):
    return Customer.objects.create(code="CUS-001", name="City Pharmacy", credit_days=0)


@pytest.fixture
def stock_in(branch, actor):
    """Post inbound stock to a batch and return the created ledger rows."""

    def _stock(batch_obj, qty, unit_cost=None, entry_type=EntryType.OPENING, business_date=None):
        return post_transactions(
            branch=branch,
            lines=[
                MovementLine(
                    medicine=batch_obj.medicine,
                    batch=batch_obj,
                    qty_delta=Decimal(str(qty)),
                    unit_cost=Decimal(str(unit_cost)) if unit_cost is not None else None,
                )
            ],
            entry_type=entry_type,
            business_date=business_date or timezone.localdate(),
            actor=actor,
        )

    return _stock
