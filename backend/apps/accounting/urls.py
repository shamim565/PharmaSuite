from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounting.views import (
    ExpenseCategoryViewSet,
    ExpenseSummaryView,
    ExpenseViewSet,
    FinancialAccountViewSet,
    IncomeCategoryViewSet,
    IncomeSummaryView,
    IncomeViewSet,
)

router = DefaultRouter()
router.register("accounts", FinancialAccountViewSet, basename="financial-account")
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("income-categories", IncomeCategoryViewSet, basename="income-category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("incomes", IncomeViewSet, basename="income")

urlpatterns = [
    path("", include(router.urls)),
    path("expenses/reports/summary/", ExpenseSummaryView.as_view(), name="report-expense-summary"),
    path("incomes/reports/summary/", IncomeSummaryView.as_view(), name="report-income-summary"),
]
