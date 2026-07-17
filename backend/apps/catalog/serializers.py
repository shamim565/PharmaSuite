from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import (
    BarcodeType,
    Generic,
    Manufacturer,
    Medicine,
    MedicineBarcode,
    MedicineBatch,
    MedicineCategory,
    MedicineUnitConversion,
    Unit,
)


class GenericSerializer(serializers.ModelSerializer):
    class Meta:
        model = Generic
        fields = ["id", "name", "therapeutic_class", "description", "is_active"]


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ["id", "name", "country", "license_no", "is_active"]


class MedicineCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")

    class Meta:
        model = MedicineCategory
        fields = ["id", "name", "parent", "parent_name", "sort_order", "is_active"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "symbol", "unit_type", "allows_fraction", "is_active"]


class MedicineUnitConversionSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    unit_symbol = serializers.CharField(source="unit.symbol", read_only=True)

    class Meta:
        model = MedicineUnitConversion
        fields = [
            "id",
            "medicine",
            "unit",
            "unit_name",
            "unit_symbol",
            "factor_to_base",
            "is_purchase_default",
            "is_sale_default",
        ]
        read_only_fields = ["medicine"]


class MedicineSerializer(serializers.ModelSerializer):
    generic_name = serializers.CharField(source="generic.name", read_only=True, default="")
    manufacturer_name = serializers.CharField(source="manufacturer.name", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    base_unit_name = serializers.CharField(source="base_unit.name", read_only=True, default="")
    barcode = serializers.CharField(required=False, allow_blank=True)
    conversions = MedicineUnitConversionSerializer(many=True, read_only=True)

    class Meta:
        model = Medicine
        fields = [
            "id",
            "code",
            "name",
            "generic",
            "generic_name",
            "manufacturer",
            "manufacturer_name",
            "category",
            "category_name",
            "base_unit",
            "base_unit_name",
            "strength",
            "dosage_form",
            "pack_size",
            "purchase_price",
            "selling_price",
            "retail_price",
            "wholesale_price",
            "custom_price",
            "mrp",
            "vat_rate",
            "reorder_level",
            "shelf_life_months",
            "near_expiry_days",
            "no_batch",
            "rx_required",
            "cold_chain",
            "is_active",
            "barcode",
            "conversions",
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

    def validate_barcode(self, value: str) -> str:
        value = value.strip()
        if value:
            qs = MedicineBarcode.objects.filter(barcode=value)
            if self.instance:
                qs = qs.exclude(medicine=self.instance)
            if qs.exists():
                raise serializers.ValidationError("Barcode already assigned to another medicine.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        primary = None
        for barcode in instance.barcodes.all():
            if barcode.barcode_type == BarcodeType.PRIMARY:
                primary = barcode
                break
        data["barcode"] = primary.barcode if primary else ""
        return data

    def create(self, validated_data):
        barcode = validated_data.pop("barcode", "")
        medicine = super().create(validated_data)
        if barcode:
            MedicineBarcode.objects.create(
                medicine=medicine, barcode=barcode, barcode_type=BarcodeType.PRIMARY
            )
        return medicine

    def update(self, instance, validated_data):
        barcode = validated_data.pop("barcode", None)
        medicine = super().update(instance, validated_data)
        if barcode:
            current = medicine.barcodes.order_by("created_at").first()
            if current is None:
                MedicineBarcode.objects.create(
                    medicine=medicine, barcode=barcode, barcode_type=BarcodeType.PRIMARY
                )
            elif current.barcode != barcode:
                current.barcode = barcode
                current.save(update_fields=["barcode", "updated_at"])
        return medicine


class MedicineBatchSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    days_to_expiry = serializers.SerializerMethodField()

    class Meta:
        model = MedicineBatch
        fields = [
            "id",
            "branch",
            "branch_name",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch_number",
            "manufacturing_date",
            "expiry_date",
            "qty_received_total",
            "qty_on_hand",
            "unit_cost",
            "status",
            "notes",
            "days_to_expiry",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "status"]

    def get_days_to_expiry(self, obj):
        if not obj.expiry_date:
            return None
        return (obj.expiry_date - timezone.localdate()).days

    def validate(self, attrs):
        medicine = attrs.get("medicine") or getattr(self.instance, "medicine", None)
        expiry = attrs.get("expiry_date", getattr(self.instance, "expiry_date", None))
        manufacturing = attrs.get("manufacturing_date", getattr(self.instance, "manufacturing_date", None))
        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
        batch_number = attrs.get("batch_number", getattr(self.instance, "batch_number", None))

        if manufacturing and expiry and expiry < manufacturing:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date must be on or after the manufacturing date."}
            )

        if medicine and not medicine.no_batch and not expiry:
            raise serializers.ValidationError({"expiry_date": "Expiry date is required for this medicine."})

        qs = MedicineBatch.objects.filter(
            branch=branch, medicine=medicine, batch_number=batch_number, expiry_date=expiry
        )
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                {"batch_number": "A batch with this number and expiry already exists for this branch."}
            )

        qty_received = attrs.get("qty_received_total")
        qty_on_hand = attrs.get("qty_on_hand")
        if self.instance is None and qty_received is not None and qty_on_hand is not None:
            if qty_on_hand != qty_received:
                raise serializers.ValidationError(
                    {
                        "qty_on_hand": (
                            "Opening quantity must equal received quantity; later corrections "
                            "are posted as inventory adjustments."
                        )
                    }
                )

        if self.instance is not None:
            immutable = ("qty_received_total", "qty_on_hand", "unit_cost")
            for field in immutable:
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {
                            field: (
                                "Quantity and cost changes must be posted as inventory "
                                "transactions, not edits."
                            )
                        }
                    )
        return attrs
