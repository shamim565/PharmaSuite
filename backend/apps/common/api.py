"""Settings and fiscal period management endpoints."""

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import APIError
from apps.common.models import FiscalPeriod
from apps.common.periods import lock_period, unlock_period
from apps.common.permissions import HasPermission
from apps.common.settings_service import SETTINGS_KEYS, get_setting_value, set_setting_value


def _grouped_settings() -> dict:
    grouped: dict[str, dict] = {}
    for key, (_category, _label, default) in SETTINGS_KEYS.items():
        value = get_setting_value(key, default=default)
        grouped.setdefault(_category, {})[key] = value
    return grouped


class SettingsView(APIView):
    permission_classes = [HasPermission]

    @property
    def required_permissions(self):
        return ["SETTINGS_MANAGE"] if self.request.method == "PUT" else ["SETTINGS_VIEW"]

    def get(self, request):
        return Response({"groups": _grouped_settings()})

    def put(self, request):
        payload = request.data or {}
        keys_by_category: dict[str, dict] = {}
        for key, value in payload.items():
            if key not in SETTINGS_KEYS:
                raise APIError("UNKNOWN_SETTING", f"Unknown setting key: {key}")
            category, _, _ = SETTINGS_KEYS[key]
            keys_by_category.setdefault(category, {})[key] = value

        for _category, entries in keys_by_category.items():
            for key, value in entries.items():
                set_setting_value(key, value, actor=request.user)
        return Response({"groups": _grouped_settings()})


class PeriodViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [HasPermission]
    required_permissions = ["PERIOD_LOCK"]
    queryset = FiscalPeriod.objects.order_by("fiscal_year", "period_month")

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get("fiscal_year")
        if year:
            qs = qs.filter(fiscal_year=year)
        return qs

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        period = self.get_object()
        from apps.accounting.models import Expense
        from apps.inventory.models import StockAdjustment

        pending_expenses = Expense.objects.filter(status="PENDING_APPROVAL").count()
        pending_adjustments = StockAdjustment.objects.filter(status="PENDING_APPROVAL").count()
        checklist = {
            "pending_expenses": pending_expenses,
            "pending_adjustments": pending_adjustments,
            "note": "Pending items cannot post into a locked period.",
        }
        period = lock_period(
            period=period, actor=request.user, reason=request.data.get("reason", ""), checklist=checklist
        )
        return Response(self._serialize(period, checklist))

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        period = unlock_period(
            period=self.get_object(), actor=request.user, reason=request.data.get("reason", "")
        )
        return Response(self._serialize(period))

    @staticmethod
    def _serialize(period: FiscalPeriod, checklist: dict | None = None) -> dict:
        data = {
            "id": str(period.id),
            "fiscal_year": period.fiscal_year,
            "period_month": period.period_month,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "status": period.status,
            "locked_by_name": period.locked_by.full_name if period.locked_by else "",
            "locked_at": period.locked_at.isoformat() if period.locked_at else None,
            "lock_reason": period.lock_reason,
            "unlock_by_name": period.unlock_by.full_name if period.unlock_by else "",
            "unlock_reason": period.unlock_reason,
        }
        if checklist is not None:
            data["checklist"] = checklist
        return data

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(
            {
                "count": queryset.count(),
                "results": [self._serialize(period) for period in queryset],
            }
        )

    def retrieve(self, request, *args, **kwargs):
        return Response(self._serialize(self.get_object()))
