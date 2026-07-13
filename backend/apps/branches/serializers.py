from rest_framework import serializers

from apps.branches.models import Branch


class BranchSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default="")

    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
            "type",
            "address",
            "phone",
            "email",
            "manager",
            "manager_name",
            "bin",
            "vat_reg",
            "trade_license",
            "invoice_prefix",
            "opening_date",
            "status",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Branch.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A branch with this code already exists.")
        return value
