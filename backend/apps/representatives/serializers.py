from rest_framework import serializers

from apps.representatives.models import (
    Representative,
    RepresentativeAssignment,
    SalesTarget,
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


class SalesTargetSerializer(serializers.ModelSerializer):
    representative_name = serializers.CharField(source="representative.name", read_only=True)
    representative_code = serializers.CharField(source="representative.code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    achieved_sales = serializers.SerializerMethodField()
    achieved_percent = serializers.SerializerMethodField()

    class Meta:
        model = SalesTarget
        fields = [
            "id",
            "representative",
            "representative_name",
            "representative_code",
            "branch",
            "branch_name",
            "fiscal_year",
            "period_month",
            "target_amount",
            "target_collection",
            "target_visits",
            "achieved_sales",
            "achieved_percent",
            "notes",
            "created_at",
        ]

    def get_achieved_sales(self, obj) -> str:
        from decimal import Decimal

        from django.db.models import Sum

        from apps.sales.models import SalesInvoice

        total = SalesInvoice.objects.filter(
            sales_rep=obj.representative,
            lifecycle="CONFIRMED",
            business_date__year=obj.fiscal_year,
            business_date__month=obj.period_month,
        ).aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
        return str(total)

    def get_achieved_percent(self, obj) -> float:
        from decimal import Decimal

        achieved = Decimal(self.get_achieved_sales(obj))
        if obj.target_amount > 0:
            return round(float(achieved / obj.target_amount * 100), 1)
        return 0.0
