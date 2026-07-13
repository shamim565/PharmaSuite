from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User, UserStatus
from apps.branches.models import Branch, BranchStatus
from apps.catalog.models import Medicine
from apps.common.permissions import HasPermission


class DashboardSummaryView(APIView):
    permission_classes = [HasPermission]
    required_permissions = ["DASHBOARD_VIEW"]

    def get(self, request):
        user = request.user
        all_branches = user.is_superuser or user.has_all_branch_scope
        branch_filter = {} if all_branches else {"id__in": user.branch_ids}

        branches = Branch.objects.filter(**branch_filter)
        users = User.objects.all()
        if not all_branches:
            users = users.filter(user_branches__branch_id__in=user.branch_ids).distinct()

        medicines = Medicine.objects.all()

        return Response(
            {
                "generated_at": timezone.now(),
                "branch_scope": "ALL" if all_branches else "ASSIGNED",
                "users": {
                    "total": users.count(),
                    "active": users.filter(status=UserStatus.ACTIVE).count(),
                },
                "branches": {
                    "total": branches.count(),
                    "active": branches.filter(status=BranchStatus.ACTIVE).count(),
                },
                "roles": {"total": Role.objects.count()},
                "medicines": {
                    "total": medicines.count(),
                    "active": medicines.filter(is_active=True).count(),
                },
                "operations": {
                    "sales_today": None,
                    "collections_today": None,
                    "customer_due": None,
                    "supplier_payable": None,
                    "stock_value": None,
                    "low_stock_count": None,
                    "near_expiry_count": None,
                },
            }
        )
