"""Backfill the inventory ledger from existing batch quantities.

Each batch with on-hand quantity becomes a single OPENING transaction, and the
stock balance cache is seeded from it. This keeps the ledger as the source of
truth from day one.
"""

from decimal import Decimal
from uuid import uuid4

from django.db import migrations


def backfill_opening_transactions(apps, schema_editor):
    MedicineBatch = apps.get_model("catalog", "MedicineBatch")
    InventoryTransaction = apps.get_model("inventory", "InventoryTransaction")
    StockBalance = apps.get_model("inventory", "StockBalance")

    for batch in MedicineBatch.objects.all():
        quantity = batch.qty_on_hand or Decimal("0")
        if quantity <= 0:
            continue
        if InventoryTransaction.objects.filter(
            batch_id=batch.id, entry_type="OPENING"
        ).exists():
            continue

        unit_cost = batch.unit_cost or Decimal("0")
        InventoryTransaction.objects.create(
            branch_id=batch.branch_id,
            medicine_id=batch.medicine_id,
            batch_id=batch.id,
            entry_type="OPENING",
            pool="SALEABLE",
            qty_delta=quantity,
            unit_cost=unit_cost,
            value_delta=(quantity * unit_cost).quantize(Decimal("0.01")),
            source_type="MEDICINE_BATCH",
            source_id=batch.id,
            source_number=batch.batch_number,
            transaction_group_id=uuid4(),
            idempotency_key=f"opening:{batch.id}",
            business_date=batch.created_at.date(),
        )
        StockBalance.objects.update_or_create(
            branch_id=batch.branch_id,
            medicine_id=batch.medicine_id,
            batch_id=batch.id,
            defaults={"qty_on_hand": quantity},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        ("catalog", "0004_normalize_medicine_masters"),
    ]

    operations = [
        migrations.RunPython(backfill_opening_transactions, noop),
    ]
