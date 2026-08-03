from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import Cheque, ChequeDirection, Payment, PaymentAllocation


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


class ChequeReadSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True, default="")
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default="")
    invoice_number = serializers.CharField(source="invoice.number", read_only=True, default="")
    supplier_payment_number = serializers.CharField(source="supplier_payment.number", read_only=True, default="")

    class Meta:
        model = Cheque
        fields = [
            "id", "direction", "status", "number", "bank_name", "bank_branch", "amount",
            "date_issued", "date_deposited", "date_cleared", "date_bounced", "date_paid",
            "date_stopped", "customer", "customer_name", "supplier", "supplier_name",
            "invoice", "invoice_number", "supplier_payment", "supplier_payment_number",
            "notes", "created_at",
        ]


class ChequeCreateSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=ChequeDirection.choices)
    number = serializers.CharField(max_length=40)
    bank_name = serializers.CharField(max_length=100)
    bank_branch = serializers.CharField(max_length=100, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    date_issued = serializers.DateField()
    customer = serializers.UUIDField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    invoice = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        from apps.sales.models import Customer, SalesInvoice
        from apps.suppliers.models import Supplier

        if attrs.get("customer") and attrs.get("supplier"):
            raise serializers.ValidationError("A cheque has either a customer or a supplier, not both.")
        if not attrs.get("customer") and not attrs.get("supplier"):
            raise serializers.ValidationError("Specify the customer (received) or supplier (issued).")
        if attrs.get("customer"):
            attrs["customer"] = Customer.objects.filter(id=attrs["customer"]).first()
            if attrs["customer"] is None:
                raise serializers.ValidationError({"customer": "Customer not found."})
            attrs["direction"] = ChequeDirection.RECEIVED
            if attrs.get("invoice"):
                attrs["invoice"] = SalesInvoice.objects.filter(
                    id=attrs["invoice"], customer=attrs["customer"]
                ).first()
        if attrs.get("supplier"):
            attrs["supplier"] = Supplier.objects.filter(id=attrs["supplier"]).first()
            if attrs["supplier"] is None:
                raise serializers.ValidationError({"supplier": "Supplier not found."})
            attrs["direction"] = ChequeDirection.ISSUED
            attrs["invoice"] = None
        return attrs
