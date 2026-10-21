from decimal import Decimal

from rest_framework import serializers

from apps.branches.models import Branch
from apps.catalog.models import Medicine
from apps.purchases.po_models import PurchaseOrder, PurchaseOrderItem
from apps.suppliers.models import Supplier


class PurchaseOrderItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    qty_pending = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    is_fully_received = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id",
            "line_no",
            "medicine",
            "medicine_name",
            "medicine_code",
            "qty_ordered",
            "qty_received",
            "qty_pending",
            "is_fully_received",
            "unit_cost",
            "line_discount",
            "vat_rate",
            "vat_amount",
            "line_net",
            "notes",
        ]


class PurchaseOrderReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.full_name", read_only=True, default="")
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default="")
    cancelled_by_name = serializers.CharField(source="cancelled_by.full_name", read_only=True, default="")
    fulfilled_by_number = serializers.CharField(source="fulfilled_by.number", read_only=True, default="")
    items = PurchaseOrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "supplier",
            "supplier_name",
            "business_date",
            "expected_delivery_date",
            "status",
            "subtotal",
            "discount_total",
            "vat_total",
            "grand_total",
            "notes",
            "submitted_at",
            "submitted_by_name",
            "approved_at",
            "approved_by_name",
            "cancel_reason",
            "cancelled_by_name",
            "fulfilled_by",
            "fulfilled_by_number",
            "created_at",
            "items",
        ]


class PurchaseOrderItemInputSerializer(serializers.Serializer):
    medicine = serializers.PrimaryKeyRelatedField(queryset=Medicine.objects.all())
    qty_ordered = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    line_discount = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"), required=False)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"), required=False)
    notes = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class PurchaseOrderCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    business_date = serializers.DateField()
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = PurchaseOrderItemInputSerializer(many=True)


class PurchaseOrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PurchaseOrderConvertSerializer(serializers.Serializer):
    supplier_invoice_number = serializers.CharField(max_length=60)
    supplier_invoice_date = serializers.DateField(required=False, allow_null=True)
