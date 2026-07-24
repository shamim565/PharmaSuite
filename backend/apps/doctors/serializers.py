from decimal import Decimal

from rest_framework import serializers

from apps.doctors.models import (
    Doctor,
    DoctorChamber,
    DoctorMedicine,
    DoctorVisit,
    DoctorVisitSample,
)


class DoctorChamberSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorChamber
        fields = ["id", "doctor", "name", "address", "visiting_hours"]


class DoctorMedicineSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)

    class Meta:
        model = DoctorMedicine
        fields = [
            "id",
            "doctor",
            "medicine",
            "medicine_name",
            "medicine_code",
            "priority",
            "strength_note",
            "effective_from",
            "effective_to",
        ]
        read_only_fields = ["doctor", "effective_from", "effective_to"]


class DoctorSerializer(serializers.ModelSerializer):
    territory_name = serializers.CharField(source="territory.name", read_only=True, default="")
    open_mapping_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "id",
            "code",
            "name",
            "gender",
            "phones",
            "email",
            "specialty",
            "degrees",
            "doctor_type",
            "registration_no",
            "category",
            "potential_rating",
            "territory",
            "territory_name",
            "visit_frequency_target",
            "consent_note",
            "notes",
            "is_active",
            "open_mapping_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_open_mapping_count(self, obj):
        return obj.medicine_mappings.filter(effective_to__isnull=True).count()

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Doctor.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A doctor with this code already exists.")
        return value

    def validate_registration_no(self, value):
        if not value:
            return None
        qs = Doctor.objects.filter(registration_no__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("This registration number is already recorded.")
        return value


class DoctorVisitSampleSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    class Meta:
        model = DoctorVisitSample
        fields = ["id", "medicine", "medicine_name", "medicine_code", "batch", "batch_number", "qty", "unit_cost"]


class DoctorVisitSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.name", read_only=True)
    doctor_code = serializers.CharField(source="doctor.code", read_only=True)
    representative_name = serializers.CharField(source="representative.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    samples = DoctorVisitSampleSerializer(many=True, read_only=True)

    class Meta:
        model = DoctorVisit
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "doctor_code",
            "representative",
            "representative_name",
            "branch",
            "branch_name",
            "status",
            "planned_date",
            "visited_at",
            "purpose",
            "products_discussed",
            "outcome",
            "next_visit_date",
            "notes",
            "missed_reason",
            "created_at",
            "samples",
        ]


class SampleInputSerializer(serializers.Serializer):
    medicine = serializers.UUIDField()
    batch = serializers.UUIDField()
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class VisitCompleteSerializer(serializers.Serializer):
    visited_at = serializers.DateTimeField(required=False)
    purpose = serializers.CharField(required=False, allow_blank=True)
    products_discussed = serializers.ListField(child=serializers.UUIDField(), required=False)
    outcome = serializers.ChoiceField(
        choices=["INTERESTED", "NEUTRAL", "NOT_INTERESTED", "PRESCRIBING"], required=False, allow_blank=True
    )
    next_visit_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    samples = SampleInputSerializer(many=True, required=False)
