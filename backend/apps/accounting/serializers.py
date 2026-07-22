from decimal import Decimal

from rest_framework import serializers

from apps.accounting.models import (
    Expense,
    ExpenseCategory,
    FinancialAccount,
    Income,
    IncomeCategory,
)


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


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_system", "is_active"]


class IncomeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeCategory
        fields = ["id", "name", "is_system", "is_active"]


class ExpenseCreateSerializer(serializers.Serializer):
    branch = serializers.UUIDField()
    category = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    account = serializers.UUIDField()
    business_date = serializers.DateField(required=False)
    payee = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ExpenseReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True, default="")
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default="")

    class Meta:
        model = Expense
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "business_date",
            "category",
            "category_name",
            "amount",
            "account",
            "account_name",
            "payee",
            "reference",
            "note",
            "status",
            "requested_by_name",
            "approved_by_name",
            "approved_at",
            "posted_at",
            "rejection_reason",
            "created_at",
        ]


class IncomeCreateSerializer(serializers.Serializer):
    branch = serializers.UUIDField()
    category = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    account = serializers.UUIDField()
    business_date = serializers.DateField(required=False)
    source = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class IncomeReadSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    posted_by_name = serializers.CharField(source="posted_by.full_name", read_only=True, default="")

    class Meta:
        model = Income
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "business_date",
            "category",
            "category_name",
            "amount",
            "account",
            "account_name",
            "source",
            "reference",
            "note",
            "status",
            "posted_by_name",
            "posted_at",
            "created_at",
        ]


class FinancialAccountWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialAccount
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "branch",
            "provider",
            "account_number",
            "allow_negative",
            "is_active",
        ]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = FinancialAccount.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("An account with this code already exists.")
        return value


class AccountAmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(required=False, allow_blank=True, default="")


class AccountTransferSerializer(serializers.Serializer):
    from_account = serializers.UUIDField()
    to_account = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(required=False, allow_blank=True, default="")
