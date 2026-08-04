"""Settings and fiscal period management endpoints."""

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_action
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
            period=period,
            actor=request.user,
            reason=request.data.get("reason", ""),
            checklist=checklist,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PERIOD_LOCKED",
            entity_type="fiscal_period",
            entity_id=period.id,
            after={"fiscal_year": period.fiscal_year, "period_month": period.period_month, "reason": request.data.get("reason", "")},
            request=request,
        )
        return Response(self._serialize(period, checklist))

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        period = unlock_period(
            period=self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        log_action(
            actor=request.user,
            action="PERIOD_UNLOCKED",
            entity_type="fiscal_period",
            entity_id=period.id,
            after={"fiscal_year": period.fiscal_year, "period_month": period.period_month, "reason": request.data.get("reason", "")},
            request=request,
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


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """User-scoped in-app notifications."""

    permission_classes = [HasPermission]
    required_permissions = []

    def get_queryset(self):
        qs = __import__("apps.common.models", fromlist=["Notification"]).Notification.objects.filter(
            user=self.request.user
        )
        unread_only = self.request.query_params.get("unread_only") == "true"
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        from apps.common.notifications import mark_read

        notification = mark_read(notification=self.get_object(), user=request.user)
        return Response(self._serialize(notification))

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        from apps.common.notifications import mark_all_read

        return Response({"updated": mark_all_read(request.user)})

    @staticmethod
    def _serialize(notification) -> dict:
        return {
            "id": str(notification.id),
            "type": notification.type,
            "severity": notification.severity,
            "title": notification.title,
            "body": notification.body,
            "deep_link": notification.deep_link,
            "payload": notification.payload,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat(),
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())[:100]
        unread = self.get_queryset().filter(is_read=False).count()
        return Response(
            {
                "count": len(queryset),
                "unread_count": unread,
                "results": [self._serialize(notification) for notification in queryset],
            }
        )

    def retrieve(self, request, *args, **kwargs):
        return Response(self._serialize(self.get_object()))


OWNER_PERMISSION_MAP = {
    "PURCHASE": "PURCHASE_MANAGE",
    "EXPENSE": "EXPENSE_POST",
    "STOCK_ADJUSTMENT": "STOCK_ADJUST",
    "DOCTOR_VISIT": "VISIT_MANAGE",
    "SALES_RETURN": "SRET_CONFIRM",
    "PURCHASE_RETURN": "PRET_CONFIRM",
}


def _attachment_permission(owner_type: str, user) -> None:
    required = OWNER_PERMISSION_MAP.get(owner_type)
    if required is None:
        return
    if not (user.is_superuser or required in user.effective_permission_codes):
        raise APIError("PERMISSION_DENIED", f"Permission {required} is required.", status_code=403)


class AttachmentView(APIView):
    permission_classes = [HasPermission]
    required_permissions = []

    def get(self, request):
        owner_type = request.query_params.get("owner_type", "")
        owner_id = request.query_params.get("owner_id", "")
        _attachment_permission(owner_type, request.user)
        from apps.common.models import Attachment

        rows = Attachment.objects.filter(owner_type=owner_type, owner_id=owner_id).order_by(
            "-created_at"
        )
        return Response(
            {
                "count": rows.count(),
                "results": [
                    {
                        "id": str(row.id),
                        "file_name": row.file_name,
                        "content_type": row.content_type,
                        "size_bytes": row.size_bytes,
                        "uploaded_by_name": row.uploaded_by.full_name if row.uploaded_by else "",
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
            }
        )

    def post(self, request):
        owner_type = request.data.get("owner_type", "")
        owner_id = request.data.get("owner_id")
        _attachment_permission(owner_type, request.user)
        if not owner_id:
            raise APIError("MISSING_OWNER", "owner_id is required.")
        import uuid

        try:
            owner_uuid = uuid.UUID(str(owner_id))
        except (ValueError, AttributeError) as exc:
            raise APIError("INVALID_OWNER", "owner_id must be a valid UUID.") from exc

        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise APIError("MISSING_FILE", "file is required.")
        from apps.common.notifications import upload_attachment

        attachment = upload_attachment(
            file=uploaded, owner_type=owner_type, owner_id=owner_uuid, actor=request.user
        )
        return Response(
            {
                "id": str(attachment.id),
                "file_name": attachment.file_name,
                "size_bytes": attachment.size_bytes,
            },
            status=201,
        )


class AttachmentDownloadView(APIView):
    permission_classes = [HasPermission]
    required_permissions = []

    def get(self, request, attachment_id):
        from django.http import FileResponse

        from apps.common.models import Attachment
        from apps.common.notifications import attachment_path

        attachment = Attachment.objects.filter(id=attachment_id).first()
        if attachment is None:
            raise APIError("NOT_FOUND", "Attachment not found.")
        _attachment_permission(attachment.owner_type, request.user)
        path = attachment_path(attachment)
        if not path.exists():
            raise APIError("NOT_FOUND", "Attachment file is missing.")
        response = FileResponse(open(path, "rb"), content_type=attachment.content_type)
        response["Content-Disposition"] = f'attachment; filename="{attachment.file_name}"'
        return response


class SearchView(APIView):
    permission_classes = [HasPermission]
    required_permissions = []

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"results": {}})

        from apps.catalog.models import Medicine
        from apps.doctors.models import Doctor
        from apps.purchases.models import Purchase
        from apps.sales.models import Customer, SalesInvoice
        from apps.suppliers.models import Supplier

        def as_list(queryset, fields):
            def value_of(row, key):
                for part in key.split("__"):
                    row = getattr(row, part, None)
                    if row is None:
                        return ""
                return str(row)

            return [
                {key: value_of(row, key) for key in fields} | {"id": str(row.id)}
                for row in queryset[:5]
            ]

        return Response({
            "results": {
                "medicines": as_list(
                    (
                        Medicine.objects.filter(name__icontains=q)
                        | Medicine.objects.filter(code__icontains=q)
                        | Medicine.objects.filter(barcodes__barcode__icontains=q)
                    ).distinct().order_by("name"),
                    ["code", "name", "selling_price"],
                ),
                "customers": as_list(
                    Customer.objects.filter(name__icontains=q).order_by("name") | Customer.objects.filter(code__icontains=q) | Customer.objects.filter(phone__icontains=q),
                    ["code", "name", "phone"],
                ),
                "suppliers": as_list(
                    Supplier.objects.filter(name__icontains=q).order_by("name") | Supplier.objects.filter(code__icontains=q),
                    ["code", "name", "phone"],
                ),
                "doctors": as_list(
                    Doctor.objects.filter(name__icontains=q).order_by("name") | Doctor.objects.filter(code__icontains=q),
                    ["code", "name", "category"],
                ),
                "invoices": as_list(
                    SalesInvoice.objects.filter(number__icontains=q).select_related("customer") | SalesInvoice.objects.filter(customer__name__icontains=q).select_related("customer"),
                    ["number", "customer__name", "grand_total", "lifecycle"],
                ),
                "purchases": as_list(
                    Purchase.objects.filter(number__icontains=q).select_related("supplier") | Purchase.objects.filter(supplier__name__icontains=q).select_related("supplier"),
                    ["number", "supplier__name", "grand_total", "lifecycle"],
                ),
            }
        })
