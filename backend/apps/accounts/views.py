from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.models import Permission, Role, User
from apps.accounts.serializers import (
    LoginSerializer,
    MeSerializer,
    PermissionSerializer,
    RoleCreateSerializer,
    RoleDetailSerializer,
    RolePermissionsWriteSerializer,
    RoleSerializer,
    RoleUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.common.exceptions import APIError
from apps.common.permissions import HasPermission
from apps.common.viewsets import PermissionMappedMixin


def _auth_response(request, user, access: str, refresh: str) -> Response:
    response = Response(
        {"access": access, "user": MeSerializer(user, context={"request": request}).data}
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        samesite="Lax",
        secure=settings.REFRESH_COOKIE_SECURE,
        path=settings.REFRESH_COOKIE_PATH,
    )
    return response


@extend_schema(request=LoginSerializer, responses=OpenApiTypes.OBJECT)
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.authenticate_user(
            request, serializer.validated_data["identifier"], serializer.validated_data["password"]
        )
        if user.totp_enabled:
            return Response(
                {"mfa_required": True, "mfa_token": services.issue_mfa_token(user)}
            )
        access, refresh = services.issue_tokens(user)
        return _auth_response(request, user, access, refresh)


@extend_schema(
    request=inline_serializer(
        "MfaLoginRequest",
        {
            "mfa_token": drf_serializers.CharField(),
            "code": drf_serializers.CharField(),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
class MfaLoginView(APIView):
    """Second login step when TOTP two-factor is enabled."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        mfa_token = str(request.data.get("mfa_token") or "")
        code = str(request.data.get("code") or "")
        user = services.complete_mfa_login(mfa_token, code)
        access, refresh = services.issue_tokens(user)
        from apps.audit.services import log_action

        log_action(
            actor=user,
            action="login_mfa",
            entity_type="User",
            entity_id=user.id,
            request=request,
        )
        return _auth_response(request, user, access, refresh)


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            raise APIError(
                "NO_REFRESH_TOKEN", "No active session. Please sign in.", status.HTTP_401_UNAUTHORIZED
            )
        user, access, new_refresh = services.handle_refresh(raw, request)
        return _auth_response(request, user, access, new_refresh)


@extend_schema(request=None, responses=OpenApiTypes.OBJECT)
class MeMfaSetupView(APIView):
    required_permissions: list[str] = []

    def post(self, request):
        secret = services.generate_totp_secret(request.user)
        return Response(
            {
                "secret": secret,
                "provisioning_uri": services.totp_provisioning_uri(request.user),
            }
        )


@extend_schema(
    request=inline_serializer("MfaCodeRequest", {"code": drf_serializers.CharField()}),
    responses=OpenApiTypes.OBJECT,
)
class MeMfaEnableView(APIView):
    required_permissions: list[str] = []

    def post(self, request):
        services.enable_totp(
            request.user, str(request.data.get("code") or ""), request=request
        )
        return Response({"totp_enabled": True})


@extend_schema(
    request=inline_serializer("MfaDisableRequest", {"code": drf_serializers.CharField()}),
    responses=OpenApiTypes.OBJECT,
)
class MeMfaDisableView(APIView):
    required_permissions: list[str] = []

    def post(self, request):
        services.disable_totp(
            request.user, str(request.data.get("code") or ""), request=request
        )
        return Response({"totp_enabled": False})


@extend_schema(request=None, responses={204: None})
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH)
        return response


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=MeSerializer)
    def patch(self, request):
        from apps.common.exceptions import APIError

        user = request.user
        default_branch_id = request.data.get("default_branch_id")
        if default_branch_id:
            if str(default_branch_id) not in [str(b) for b in user.branch_ids]:
                raise APIError(
                    "BRANCH_NOT_ASSIGNED",
                    "You can only switch to a branch assigned to you.",
                    status_code=403,
                )
            user.default_branch_id = default_branch_id
            user.save(update_fields=["default_branch_id", "updated_at"])
        return Response(MeSerializer(user, context={"request": request}).data)


class UserViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["USER_VIEW"],
        "retrieve": ["USER_VIEW"],
        "create": ["USER_MANAGE"],
        "update": ["USER_MANAGE"],
        "partial_update": ["USER_MANAGE"],
        "deactivate": ["USER_MANAGE"],
        "activate": ["USER_MANAGE"],
        "reset_2fa": ["USER_MANAGE"],
    }
    permission_classes = [HasPermission]
    filterset_fields = ["status", "user_roles__role__code"]
    search_fields = ["full_name", "mobile", "email"]
    ordering_fields = ["full_name", "created_at", "last_login_at"]
    ordering = ["full_name"]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.all().prefetch_related(
            "user_roles__role", "user_branches__branch", "password_history"
        )
        if user.is_superuser or user.has_all_branch_scope:
            return qs
        return qs.filter(user_branches__branch_id__in=user.branch_ids).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user(request.user, serializer.validated_data, request=request)
        return Response(UserSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.update_user(request.user, user, serializer.validated_data, request=request)
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.set_user_status(request.user, self.get_object(), active=False, request=request)
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.set_user_status(request.user, self.get_object(), active=True, request=request)
        return Response(UserSerializer(user, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="reset-2fa")
    def reset_2fa(self, request, pk=None):
        user = services.reset_totp(request.user, self.get_object(), request=request)
        return Response(UserSerializer(user, context={"request": request}).data)


class RoleViewSet(
    PermissionMappedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_map = {
        "list": ["ROLE_VIEW"],
        "retrieve": ["ROLE_VIEW"],
        "create": ["ROLE_MANAGE"],
        "update": ["ROLE_MANAGE"],
        "partial_update": ["ROLE_MANAGE"],
        "set_permissions": ["ROLE_MANAGE"],
    }
    permission_classes = [HasPermission]
    queryset = Role.objects.all().prefetch_related("role_permissions__permission")
    search_fields = ["code", "name"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "create":
            return RoleCreateSerializer
        if self.action in ("update", "partial_update"):
            return RoleUpdateSerializer
        if self.action == "retrieve":
            return RoleDetailSerializer
        return RoleSerializer

    def create(self, request, *args, **kwargs):
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.create_role(request.user, serializer.validated_data, request=request)
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        role = self.get_object()
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.update_role(request.user, role, serializer.validated_data, request=request)
        return Response(RoleDetailSerializer(role).data)

    @action(detail=True, methods=["put"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        role = self.get_object()
        serializer = RolePermissionsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.replace_role_permissions(
            request.user, role, serializer.validated_data["permissions"], request=request
        )
        return Response(RoleDetailSerializer(role).data)


@extend_schema(responses=PermissionSerializer(many=True))
class PermissionListView(APIView):
    permission_classes = [HasPermission]
    required_permissions = []

    def get(self, request):
        user = request.user
        if not (
            user.is_superuser
            or user.effective_permission_codes & {"ROLE_VIEW", "ROLE_MANAGE"}
        ):
            raise APIError(
                "PERMISSION_DENIED",
                "ROLE_VIEW or ROLE_MANAGE is required.",
                status_code=403,
            )
        module = request.query_params.get("module")
        qs = Permission.objects.all()
        if module:
            qs = qs.filter(module=module)
        grouped: dict[str, list] = {}
        for permission in qs:
            grouped.setdefault(permission.module, []).append(PermissionSerializer(permission).data)
        return Response(grouped)
