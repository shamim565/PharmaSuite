from rest_framework import serializers

from apps.suppliers.models import Supplier, SupplierLedgerEntry


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "code",
            "name",
            "supplier_type",
            "contact_person",
            "phone",
            "email",
            "address",
            "bin",
            "vat_reg",
            "trade_license",
            "credit_days",
            "preferred_payment_method",
            "bank_details",
            "excess_return_handling",
            "balance_cache",
            "is_active",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "balance_cache", "created_at"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Supplier.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A supplier with this code already exists.")
        return value


class SupplierLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierLedgerEntry
        fields = [
            "id",
            "supplier",
            "branch",
            "entry_type",
            "amount_delta",
            "due_date",
            "source_type",
            "source_number",
            "business_date",
            "created_at",
        ]
