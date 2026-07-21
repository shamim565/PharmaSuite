from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import (
    InventoryTransaction,
    StockAdjustment,
    StockAdjustmentItem,
    StockBalance,
)


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


class StockAdjustmentItemInputSerializer(serializers.Serializer):
    medicine = serializers.UUIDField()
    batch = serializers.UUIDField()
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    pool = serializers.ChoiceField(choices=["SALEABLE", "PROMO", "QUARANTINE"], default="SALEABLE")
    target_pool = serializers.ChoiceField(
        choices=["SALEABLE", "PROMO", "QUARANTINE"], required=False, allow_null=True
    )
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, allow_null=True, min_value=Decimal("0")
    )


class StockAdjustmentCreateSerializer(serializers.Serializer):
    branch = serializers.UUIDField()
    adjustment_type = serializers.ChoiceField(choices=["INCREASE", "DECREASE"])
    reason_code = serializers.ChoiceField(
        choices=[
            "DATA_CORRECTION",
            "COUNT_VARIANCE",
            "DAMAGE",
            "EXPIRY_WRITE_OFF",
            "FOUND_STOCK",
            "PROMO_REPLENISH",
            "RECALL_DISPOSAL",
        ]
    )
    business_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = StockAdjustmentItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["adjustment_type"] == "INCREASE" and any(
            row.get("target_pool") for row in attrs["items"]
        ):
            raise serializers.ValidationError(
                {"target_pool": "target_pool only applies to decrease (move) adjustments."}
            )
        return attrs


class StockAdjustmentItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    class Meta:
        model = StockAdjustmentItem
        fields = [
            "id",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "qty",
            "pool",
            "target_pool",
            "unit_cost",
        ]


class StockAdjustmentReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True, default="")
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default="")
    items = StockAdjustmentItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "business_date",
            "adjustment_type",
            "reason_code",
            "status",
            "total_value",
            "requested_by_name",
            "approved_by_name",
            "approved_at",
            "posted_at",
            "rejection_reason",
            "reversal_of",
            "notes",
            "created_at",
            "items",
        ]
