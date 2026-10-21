from decimal import Decimal

from django.db.models import Count, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import (
    Expense,
    ExpenseCategory,
    FinancialAccount,
    Income,
    IncomeCategory,
)
from apps.accounting.serializers import (
    AccountAmountSerializer,
    AccountTransferSerializer,
    ExpenseCategorySerializer,
    ExpenseCreateSerializer,
    ExpenseReadSerializer,
    FinancialAccountSerializer,
    FinancialAccountWriteSerializer,
    IncomeCategorySerializer,
    IncomeCreateSerializer,
    IncomeReadSerializer,
)
from apps.accounting.services import (
    approve_expense,
    create_expense,
    create_income,
    deposit_to_account,
    reject_expense,
    reverse_expense,
    reverse_income,
    transfer_between_accounts,
    withdraw_from_account,
)
from apps.audit.services import log_action
from apps.branches.models import Branch
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.schema import object_response
from apps.common.viewsets import PermissionMappedMixin


def scoped(user, queryset, field: str = "branch_id"):
    if user.is_superuser or user.has_all_branch_scope:
        return queryset
    return queryset.filter(**{f"{field}__in": user.branch_ids})


class FinancialAccountViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["ACCOUNT_VIEW"],
        "retrieve": ["ACCOUNT_VIEW"],
        "ledger": ["ACCOUNT_VIEW"],
        "create": ["ACCOUNT_MANAGE"],
        "update": ["ACCOUNT_MANAGE"],
        "partial_update": ["ACCOUNT_MANAGE"],
        "deposit": ["ACCOUNT_MANAGE"],
        "withdraw": ["ACCOUNT_MANAGE"],
        "transfer": ["ACCOUNT_MANAGE"],
    }
    permission_classes = [HasPermission]
    queryset = FinancialAccount.objects.select_related("branch")
    filterset_fields = ["account_type", "branch", "is_active"]
    search_fields = ["code", "name", "provider"]
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.has_all_branch_scope:
            return qs
        from django.db.models import Q

        return qs.filter(Q(branch_id__in=user.branch_ids) | Q(branch__isnull=True))

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FinancialAccountWriteSerializer
        return FinancialAccountSerializer

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        account = self.get_object()
        entries = account.transactions.order_by("-created_at", "-id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            entries = entries.filter(business_date__gte=date_from)
        if date_to:
            entries = entries.filter(business_date__lte=date_to)

        entries = list(entries[:500])
        balance = Decimal("0")
        rows = []
        for entry in reversed(entries):
            balance += entry.amount_delta
            rows.append(
                {
                    "id": str(entry.id),
                    "entry_type": entry.entry_type,
                    "amount_delta": str(entry.amount_delta),
                    "reference": entry.reference,
                    "source_type": entry.source_type,
                    "source_number": entry.source_number,
                    "business_date": entry.business_date,
                    "running_balance": str(balance),
                }
            )
        rows.reverse()
        return Response({"balance": str(account.balance_cache), "count": len(rows), "results": rows})

    @action(detail=True, methods=["post"])
    def deposit(self, request, pk=None):
        serializer = AccountAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = deposit_to_account(
            account=self.get_object(),
            amount=serializer.validated_data["amount"],
            reference=serializer.validated_data.get("reference", ""),
            actor=request.user,
        )
        return Response({"id": str(txn.id), "entry_type": txn.entry_type, "amount": str(txn.amount_delta)})

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        serializer = AccountAmountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = withdraw_from_account(
            account=self.get_object(),
            amount=serializer.validated_data["amount"],
            reference=serializer.validated_data.get("reference", ""),
            actor=request.user,
        )
        return Response({"id": str(txn.id), "entry_type": txn.entry_type, "amount": str(txn.amount_delta)})

    @action(detail=False, methods=["post"])
    def transfer(self, request):
        serializer = AccountTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from_account = FinancialAccount.objects.filter(id=data["from_account"]).first()
        to_account = FinancialAccount.objects.filter(id=data["to_account"]).first()
        if from_account is None or to_account is None:
            raise APIError("INVALID_ACCOUNT", "Transfer account not found.")
        group_id, _, _ = transfer_between_accounts(
            from_account=from_account,
            to_account=to_account,
            amount=data["amount"],
            reference=data.get("reference", ""),
            actor=request.user,
        )
        return Response({"transfer_group_id": str(group_id), "status": "posted"}, status=status.HTTP_201_CREATED)


class ExpenseCategoryViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["EXPENSE_VIEW"],
        "create": ["EXPENSE_POST"],
        "update": ["EXPENSE_POST"],
        "partial_update": ["EXPENSE_POST"],
    }
    permission_classes = [HasPermission]
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()
    search_fields = ["name"]
    ordering = ["name"]


class IncomeCategoryViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["INCOME_VIEW"],
        "create": ["INCOME_POST"],
        "update": ["INCOME_POST"],
        "partial_update": ["INCOME_POST"],
    }
    permission_classes = [HasPermission]
    serializer_class = IncomeCategorySerializer
    queryset = IncomeCategory.objects.all()
    search_fields = ["name"]
    ordering = ["name"]


class ExpenseViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["EXPENSE_VIEW"],
        "retrieve": ["EXPENSE_VIEW"],
        "create": ["EXPENSE_POST"],
        "approve": ["EXPENSE_APPROVE"],
        "reject": ["EXPENSE_APPROVE"],
        "reverse": ["EXPENSE_POST"],
    }
    permission_classes = [HasPermission]
    queryset = Expense.objects.select_related("branch", "category", "account", "requested_by", "approved_by")
    filterset_fields = ["branch", "category", "account", "status"]
    search_fields = ["number", "payee", "reference", "note"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = ExpenseReadSerializer

    def get_queryset(self):
        return scoped(self.request.user, super().get_queryset())

    def create(self, request):
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        branch = Branch.objects.filter(id=data["branch"]).first()
        category = ExpenseCategory.objects.filter(id=data["category"], is_active=True).first()
        account = FinancialAccount.objects.filter(id=data["account"], is_active=True).first()
        if branch is None or category is None or account is None:
            raise APIError("INVALID_REFERENCE", "Branch, category or account not found or inactive.")
        expense = create_expense(
            branch=branch,
            category=category,
            amount=data["amount"],
            account=account,
            business_date=data.get("business_date"),
            payee=data.get("payee", ""),
            reference=data.get("reference", ""),
            note=data.get("note", ""),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="EXPENSE_POSTED",
            entity_type="expense",
            entity_id=expense.id,
            after={"number": expense.number or "", "amount": str(expense.amount), "category": str(expense.category_id)},
            branch=expense.branch,
            request=request,
        )
        return Response(ExpenseReadSerializer(expense).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        expense = approve_expense(expense=self.get_object(), actor=request.user)
        return Response(ExpenseReadSerializer(expense).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        expense = reject_expense(
            expense=self.get_object(), actor=request.user, reason=request.data.get("reason", "")
        )
        return Response(ExpenseReadSerializer(expense).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        expense = reverse_expense(
            expense=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="EXPENSE_REVERSED",
            entity_type="expense",
            entity_id=expense.id,
            after={"number": expense.number or "", "amount": str(expense.amount)},
            branch=expense.branch,
            request=request,
        )
        return Response(ExpenseReadSerializer(expense).data)


class IncomeViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["INCOME_VIEW"],
        "retrieve": ["INCOME_VIEW"],
        "create": ["INCOME_POST"],
        "reverse": ["INCOME_POST"],
    }
    permission_classes = [HasPermission]
    queryset = Income.objects.select_related("branch", "category", "account", "posted_by")
    filterset_fields = ["branch", "category", "account", "status"]
    search_fields = ["number", "source", "reference", "note"]
    ordering = ["-business_date", "-created_at"]
    serializer_class = IncomeReadSerializer

    def get_queryset(self):
        return scoped(self.request.user, super().get_queryset())

    def create(self, request):
        serializer = IncomeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        branch = Branch.objects.filter(id=data["branch"]).first()
        category = IncomeCategory.objects.filter(id=data["category"], is_active=True).first()
        account = FinancialAccount.objects.filter(id=data["account"], is_active=True).first()
        if branch is None or category is None or account is None:
            raise APIError("INVALID_REFERENCE", "Branch, category or account not found or inactive.")
        income = create_income(
            branch=branch,
            category=category,
            amount=data["amount"],
            account=account,
            business_date=data.get("business_date"),
            source=data.get("source", ""),
            reference=data.get("reference", ""),
            note=data.get("note", ""),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="INCOME_POSTED",
            entity_type="income",
            entity_id=income.id,
            after={"number": income.number or "", "amount": str(income.amount), "category": str(income.category_id)},
            branch=income.branch,
            request=request,
        )
        return Response(IncomeReadSerializer(income).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        income = reverse_income(
            income=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="INCOME_REVERSED",
            entity_type="income",
            entity_id=income.id,
            after={"number": income.number or "", "amount": str(income.amount)},
            branch=income.branch,
            request=request,
        )
        return Response(IncomeReadSerializer(income).data)


def _period_filter(qs, request):
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        qs = qs.filter(business_date__gte=date_from)
    if date_to:
        qs = qs.filter(business_date__lte=date_to)
    return qs


@object_response
class ExpenseSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["EXPENSE_VIEW"]

    def get(self, request):
        qs = scoped(
            request.user,
            Expense.objects.filter(status="POSTED"),
        )
        qs = _period_filter(qs, request)
        rows = (
            qs.values("category_id", "category__name")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("category__name")
        )
        results = [
            {
                "category": row["category_id"],
                "category_name": row["category__name"],
                "total": str(row["total"]),
                "count": row["count"],
            }
            for row in rows
        ]
        total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return Response({"count": len(results), "total": str(total), "results": results})


@object_response
class IncomeSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["INCOME_VIEW"]

    def get(self, request):
        qs = scoped(
            request.user,
            Income.objects.filter(status="POSTED"),
        )
        qs = _period_filter(qs, request)
        rows = (
            qs.values("category_id", "category__name")
            .annotate(total=Sum("amount"))
            .order_by("category__name")
        )
        results = [
            {"category": row["category_id"], "category_name": row["category__name"], "total": str(row["total"])}
            for row in rows
        ]
        total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return Response({"count": len(results), "total": str(total), "results": results})