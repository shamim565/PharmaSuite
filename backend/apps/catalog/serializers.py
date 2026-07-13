from rest_framework import serializers

from apps.catalog.models import Medicine


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = [
            "id",
            "code",
            "name",
            "generic_name",
            "manufacturer",
            "category",
            "strength",
            "dosage_form",
            "unit",
            "pack_size",
            "purchase_price",
            "selling_price",
            "mrp",
            "vat_rate",
            "reorder_level",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def validate_vat_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("VAT rate must be between 0 and 100.")
        return value
