from decimal import Decimal

from rest_framework import serializers

from apps.branches.models import Branch
from apps.inventory.models import StockAdjustment
from apps.purchases.credit_models import SupplierCreditNote, SupplierCreditNoteReason
from apps.suppliers.models import Supplier


class SupplierCreditNoteReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    settled_by_name = serializers.CharField(source="settled_by.full_name", read_only=True, default="")
    adjustment_number = serializers.CharField(source="adjustment.number", read_only=True, default="")
    days_open = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = SupplierCreditNote
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "supplier",
            "supplier_name",
            "business_date",
            "amount",
            "reason_code",
            "reference",
            "status",
            "notes",
            "adjustment",
            "adjustment_number",
            "days_open",
            "settled_at",
            "settled_by_name",
            "cancel_reason",
            "created_at",
        ]


class SupplierCreditNoteCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    business_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reason_code = serializers.ChoiceField(choices=SupplierCreditNoteReason.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    adjustment = serializers.PrimaryKeyRelatedField(
        queryset=StockAdjustment.objects.all(), required=False, allow_null=True
    )


class SupplierCreditNoteSettleSerializer(serializers.Serializer):
    pass


class SupplierCreditNoteCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
