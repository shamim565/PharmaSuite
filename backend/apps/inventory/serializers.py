from rest_framework import serializers

from apps.inventory.models import InventoryTransaction, StockBalance


class InventoryTransactionSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    actor_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = InventoryTransaction
        fields = [
            "id",
            "branch",
            "branch_name",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "entry_type",
            "pool",
            "qty_delta",
            "unit_cost",
            "value_delta",
            "source_type",
            "source_number",
            "transaction_group_id",
            "business_date",
            "actor_name",
            "created_at",
        ]


class StockBalanceSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    expiry_date = serializers.DateField(source="batch.expiry_date", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    reorder_level = serializers.DecimalField(
        source="medicine.reorder_level", max_digits=14, decimal_places=3, read_only=True
    )

    class Meta:
        model = StockBalance
        fields = [
            "id",
            "branch",
            "branch_name",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "expiry_date",
            "qty_on_hand",
            "qty_promo",
            "qty_quarantine",
            "reorder_level",
            "updated_at",
        ]
