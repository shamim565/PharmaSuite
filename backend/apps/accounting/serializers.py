from rest_framework import serializers

from apps.accounting.models import FinancialAccount


class FinancialAccountSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = FinancialAccount
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "branch",
            "branch_name",
            "provider",
            "account_number",
            "allow_negative",
            "balance_cache",
            "is_active",
        ]
