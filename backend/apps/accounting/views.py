from rest_framework import mixins, viewsets

from apps.accounting.models import FinancialAccount
from apps.accounting.serializers import FinancialAccountSerializer
from apps.common.permissions import HasPermission


class FinancialAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [HasPermission]
    required_permissions = ["ACCOUNT_VIEW"]
    serializer_class = FinancialAccountSerializer
    queryset = FinancialAccount.objects.select_related("branch")
    filterset_fields = ["account_type", "branch", "is_active"]
    search_fields = ["code", "name", "provider"]
    ordering = ["name"]
