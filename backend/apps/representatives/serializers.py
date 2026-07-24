from rest_framework import serializers

from apps.representatives.models import (
    Representative,
    RepresentativeAssignment,
    Territory,
)


class TerritorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")

    class Meta:
        model = Territory
        fields = ["id", "name", "parent", "parent_name", "territory_type", "is_active"]


class RepresentativeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    user_name = serializers.CharField(source="user.full_name", read_only=True, default="")
    reports_to_name = serializers.CharField(source="reports_to.name", read_only=True, default="")

    class Meta:
        model = Representative
        fields = [
            "id",
            "code",
            "name",
            "rep_type",
            "phone",
            "email",
            "branch",
            "branch_name",
            "user",
            "user_name",
            "reports_to",
            "reports_to_name",
            "joined_at",
            "is_active",
            "notes",
        ]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Representative.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A representative with this code already exists.")
        return value


class RepresentativeAssignmentSerializer(serializers.ModelSerializer):
    representative_name = serializers.CharField(source="representative.name", read_only=True)
    entity_label = serializers.SerializerMethodField()

    class Meta:
        model = RepresentativeAssignment
        fields = [
            "id",
            "representative",
            "representative_name",
            "entity_type",
            "entity_id",
            "entity_label",
            "effective_from",
            "effective_to",
            "is_primary",
        ]

    def get_entity_label(self, obj):
        from apps.doctors.models import Doctor
        from apps.sales.models import Customer

        if obj.entity_type == "DOCTOR":
            doctor = Doctor.objects.filter(id=obj.entity_id).first()
            return doctor.name if doctor else str(obj.entity_id)
        if obj.entity_type == "CUSTOMER":
            customer = Customer.objects.filter(id=obj.entity_id).first()
            return customer.name if customer else str(obj.entity_id)
        territory = Territory.objects.filter(id=obj.entity_id).first()
        return territory.name if territory else str(obj.entity_id)
