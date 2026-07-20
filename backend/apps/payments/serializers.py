from rest_framework import serializers

from apps.payments.models import Payment, PaymentAllocation


class PaymentAllocationInputSerializer(serializers.Serializer):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)


class CustomerPaymentCreateSerializer(serializers.Serializer):
    customer = serializers.UUIDField()
    branch = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    method = serializers.ChoiceField(choices=["CASH", "BANK", "MFS", "CHEQUE"])
    account = serializers.UUIDField()
    business_date = serializers.DateField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = PaymentAllocationInputSerializer(many=True, required=False, allow_null=True)


class PaymentAllocationReadSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "invoice", "invoice_number", "amount"]


class CustomerPaymentReadSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    collector_name = serializers.CharField(source="collector.full_name", read_only=True, default="")
    allocations = PaymentAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "customer",
            "customer_name",
            "business_date",
            "amount",
            "method",
            "account",
            "account_name",
            "reference",
            "collector_name",
            "status",
            "allocations",
            "created_at",
        ]
