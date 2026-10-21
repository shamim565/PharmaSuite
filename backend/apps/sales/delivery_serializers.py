from rest_framework import serializers

from apps.branches.models import Branch
from apps.catalog.models import Medicine, MedicineBatch
from apps.sales.delivery_models import DeliveryChallan, DeliveryChallanItem
from apps.sales.models import Customer, SalesInvoice


class DeliveryChallanItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)

    class Meta:
        model = DeliveryChallanItem
        fields = [
            "id",
            "line_no",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "qty",
            "notes",
        ]


class DeliveryChallanReadSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True, default="")
    dispatched_by_name = serializers.CharField(source="dispatched_by.full_name", read_only=True, default="")
    delivered_by_name = serializers.CharField(source="delivered_by.full_name", read_only=True, default="")
    items = DeliveryChallanItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryChallan
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "customer",
            "customer_name",
            "customer_code",
            "invoice",
            "invoice_number",
            "business_date",
            "status",
            "delivery_person",
            "delivery_phone",
            "vehicle_no",
            "dispatched_at",
            "dispatched_by_name",
            "delivered_at",
            "delivered_by_name",
            "recipient_name",
            "recipient_phone",
            "notes",
            "cancel_reason",
            "created_at",
            "items",
        ]


class DeliveryChallanItemInputSerializer(serializers.Serializer):
    medicine = serializers.PrimaryKeyRelatedField(queryset=Medicine.objects.all())
    batch = serializers.PrimaryKeyRelatedField(queryset=MedicineBatch.objects.all(), required=False, allow_null=True)
    batch_number = serializers.CharField(max_length=60, required=False, default="DEFAULT")
    qty = serializers.DecimalField(max_digits=14, decimal_places=3)
    notes = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class DeliveryChallanCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    invoice = serializers.PrimaryKeyRelatedField(queryset=SalesInvoice.objects.all(), required=False, allow_null=True)
    business_date = serializers.DateField()
    delivery_person = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    delivery_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    vehicle_no = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = DeliveryChallanItemInputSerializer(many=True)


class DeliveryChallanFromInvoiceSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=SalesInvoice.objects.all())
    delivery_person = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    delivery_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    vehicle_no = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class DeliveryChallanCompleteSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    recipient_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class DeliveryChallanCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
