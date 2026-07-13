from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    BranchScope,
    LoginAttempt,
    PasswordHistory,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
    UserStatus,
)
from apps.audit.services import log_action
from apps.common.exceptions import APIError, ConflictError, NotFoundError


def client_meta(request) -> dict:
    if request is None:
        return {"ip": None, "user_agent": ""}
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return {"ip": ip, "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]}


def find_user(identifier: str) -> User | None:
    return User.objects.filter(Q(mobile=identifier) | Q(email__iexact=identifier)).first()


def _record_attempt(identifier: str, user: User | None, request, success: bool, reason: str = "") -> None:
    meta = client_meta(request)
    LoginAttempt.objects.create(
        identifier=identifier,
        user=user,
        ip=meta["ip"],
        user_agent=meta["user_agent"],
        success=success,
        failure_reason=reason,
    )


def authenticate_user(request, identifier: str, password: str) -> User:
    user = find_user(identifier)

    if user is None:
        _record_attempt(identifier, None, request, False, "UNKNOWN_USER")
        raise APIError("INVALID_CREDENTIALS", "Invalid credentials.", status.HTTP_401_UNAUTHORIZED)

    if user.is_locked:
        _record_attempt(identifier, user, request, False, "LOCKED")
        raise APIError(
            "ACCOUNT_LOCKED",
            "Account is temporarily locked due to failed attempts. Try again later.",
            status.HTTP_423_LOCKED,
        )

    if user.status != UserStatus.ACTIVE:
        _record_attempt(identifier, user, request, False, "INACTIVE")
        raise APIError("INVALID_CREDENTIALS", "Invalid credentials.", status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(password):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        user.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        _record_attempt(identifier, user, request, False, "BAD_PASSWORD")
        log_action(
            actor=user,
            action="login_failed",
            entity_type="User",
            entity_id=user.id,
            request=request,
        )
        raise APIError("INVALID_CREDENTIALS", "Invalid credentials.", status.HTTP_401_UNAUTHORIZED)

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = timezone.now()
    user.last_login = timezone.now()
    user.save(update_fields=["failed_attempts", "locked_until", "last_login_at", "last_login", "updated_at"])
    _record_attempt(identifier, user, request, True)
    log_action(actor=user, action="login", entity_type="User", entity_id=user.id, request=request)
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def revoke_all_sessions(user: User) -> int:
    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    return count


def handle_refresh(raw_token: str, request) -> tuple[User, str, str]:
    """Rotate a refresh token; on failure, revoke the family when the token is identifiable."""
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import UntypedToken

    try:
        refresh = RefreshToken(raw_token)
    except TokenError as exc:
        user = None
        try:
            payload = UntypedToken(raw_token)
            user = User.objects.filter(id=payload.get("user_id")).first()
        except TokenError:
            payload = None
        if user is not None:
            revoke_all_sessions(user)
            log_action(
                actor=None,
                action="refresh_reuse_detected",
                entity_type="User",
                entity_id=user.id,
                request=request,
                after={"reason": str(exc)},
            )
        raise APIError(
            "INVALID_REFRESH_TOKEN",
            "Session expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc

    user = User.objects.filter(id=refresh.get("user_id")).first()
    if user is None or user.status != UserStatus.ACTIVE:
        raise APIError("INVALID_REFRESH_TOKEN", "Session expired. Please sign in again.", status.HTTP_401_UNAUTHORIZED)

    access = str(refresh.access_token)
    refresh.blacklist()
    new_refresh = RefreshToken.for_user(user)
    return user, access, str(new_refresh)


def validate_password_policy(user: User, raw_password: str) -> None:
    try:
        validate_password(raw_password, user=user)
    except DjangoValidationError as exc:
        raise APIError("WEAK_PASSWORD", " ".join(exc.messages), status.HTTP_400_BAD_REQUEST) from exc

    history = user.password_history.order_by("-created_at")[: settings.PASSWORD_HISTORY_SIZE]
    for entry in history:
        if check_password(raw_password, entry.password_hash):
            raise APIError(
                "PASSWORD_REUSED",
                "Password was used recently. Choose a different password.",
                status.HTTP_400_BAD_REQUEST,
            )


def push_password_history(user: User, old_hash: str) -> None:
    PasswordHistory.objects.create(user=user, password_hash=old_hash)
    keep = settings.PASSWORD_HISTORY_SIZE
    ids = list(user.password_history.order_by("-created_at").values_list("id", flat=True)[keep:])
    if ids:
        PasswordHistory.objects.filter(id__in=ids).delete()


def change_password(user: User, new_password: str, *, actor=None, request=None) -> None:
    validate_password_policy(user, new_password)
    old_hash = user.password
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    push_password_history(user, old_hash)
    revoke_all_sessions(user)
    log_action(
        actor=actor or user,
        action="password_changed",
        entity_type="User",
        entity_id=user.id,
        request=request,
    )


def _snapshot_user(user: User) -> dict:
    return {
        "full_name": user.full_name,
        "mobile": user.mobile,
        "email": user.email,
        "status": user.status,
        "is_superuser": user.is_superuser,
        "roles": sorted(user.user_roles.values_list("role__code", flat=True)),
        "branches": sorted(user.user_branches.values_list("branch__code", flat=True)),
    }


def _assign_roles_and_branches(user: User, role_ids, branch_ids, default_branch_id) -> None:
    if role_ids is not None:
        UserRole.objects.filter(user=user).delete()
        UserRole.objects.bulk_create(
            [UserRole(user=user, role_id=rid) for rid in set(role_ids)]
        )
    if branch_ids is not None:
        UserBranch.objects.filter(user=user).delete()
        UserBranch.objects.bulk_create(
            [
                UserBranch(user=user, branch_id=bid, is_default=(str(bid) == str(default_branch_id)))
                for bid in set(branch_ids)
            ]
        )
    if default_branch_id is not None:
        UserBranch.objects.filter(user=user).update(is_default=False)
        UserBranch.objects.filter(user=user, branch_id=default_branch_id).update(is_default=True)
        user.default_branch_id = default_branch_id
        user.save(update_fields=["default_branch", "updated_at"])


@transaction.atomic
def create_user(actor: User, data: dict, request=None) -> User:
    if User.objects.filter(mobile=data["mobile"]).exists():
        raise ConflictError("MOBILE_TAKEN", "A user with this mobile number already exists.")
    if data.get("email") and User.objects.filter(email__iexact=data["email"]).exists():
        raise ConflictError("EMAIL_TAKEN", "A user with this email already exists.")

    user = User(
        full_name=data["full_name"],
        mobile=data["mobile"],
        email=data.get("email") or None,
        status=UserStatus.ACTIVE,
    )
    user.set_password(data["password"])
    user.save()

    _assign_roles_and_branches(
        user, data.get("role_ids"), data.get("branch_ids"), data.get("default_branch_id")
    )
    log_action(
        actor=actor,
        action="user_created",
        entity_type="User",
        entity_id=user.id,
        after=_snapshot_user(user),
        request=request,
    )
    return user


@transaction.atomic
def update_user(actor: User, user: User, data: dict, request=None) -> User:
    before = _snapshot_user(user)

    if "email" in data and data["email"]:
        if User.objects.filter(email__iexact=data["email"]).exclude(id=user.id).exists():
            raise ConflictError("EMAIL_TAKEN", "A user with this email already exists.")

    for field in ("full_name", "email"):
        if field in data:
            setattr(user, field, data[field] or None if field == "email" else data[field])

    if "status" in data and data["status"]:
        set_user_status(actor, user, active=data["status"] == UserStatus.ACTIVE, request=request)

    user.save()
    _assign_roles_and_branches(
        user,
        data.get("role_ids"),
        data.get("branch_ids"),
        data.get("default_branch_id"),
    )
    log_action(
        actor=actor,
        action="user_updated",
        entity_type="User",
        entity_id=user.id,
        before=before,
        after=_snapshot_user(user),
        request=request,
    )
    return user


@transaction.atomic
def set_user_status(actor: User, user: User, *, active: bool, request=None) -> User:
    if user.id == actor.id and not active:
        raise ConflictError("CANNOT_DEACTIVATE_SELF", "You cannot deactivate your own account.")

    if not active and user.user_roles.filter(role__code="OWNER").exists():
        remaining = (
            User.objects.filter(status=UserStatus.ACTIVE, user_roles__role__code="OWNER")
            .exclude(id=user.id)
            .count()
        )
        if remaining == 0:
            raise ConflictError("LAST_OWNER", "The last active owner cannot be deactivated.")

    before = {"status": user.status}
    user.status = UserStatus.ACTIVE if active else UserStatus.DEACTIVATED
    user.save(update_fields=["status", "updated_at"])

    if not active:
        user._permission_cache = None
        revoke_all_sessions(user)

    log_action(
        actor=actor,
        action="user_activated" if active else "user_deactivated",
        entity_type="User",
        entity_id=user.id,
        before=before,
        after={"status": user.status},
        request=request,
    )
    return user


@transaction.atomic
def replace_role_permissions(actor: User, role: Role, permissions: list[dict], request=None) -> Role:
    before = list(
        role.role_permissions.values_list("permission__code", "effect")
    )
    role.role_permissions.all().delete()

    codes = [row["code"] for row in permissions]
    permission_map = {p.code: p for p in Permission.objects.filter(code__in=codes)}
    missing = sorted(set(codes) - set(permission_map))
    if missing:
        raise NotFoundError("UNKNOWN_PERMISSION", f"Unknown permissions: {', '.join(missing)}")

    RolePermission.objects.bulk_create(
        [
            RolePermission(
                role=role,
                permission=permission_map[row["code"]],
                effect=row.get("effect", "ALLOW"),
            )
            for row in permissions
        ]
    )
    after = list(role.role_permissions.values_list("permission__code", "effect"))
    log_action(
        actor=actor,
        action="role_permissions_updated",
        entity_type="Role",
        entity_id=role.id,
        before={"permissions": sorted(before)},
        after={"permissions": sorted(after)},
        request=request,
    )
    return role


def create_role(actor: User, data: dict, request=None) -> Role:
    if Role.objects.filter(code__iexact=data["code"]).exists():
        raise ConflictError("ROLE_CODE_TAKEN", "A role with this code already exists.")
    role = Role.objects.create(
        code=data["code"].upper(),
        name=data["name"],
        description=data.get("description", ""),
        branch_scope=data.get("branch_scope", BranchScope.ASSIGNED),
    )
    log_action(
        actor=actor,
        action="role_created",
        entity_type="Role",
        entity_id=role.id,
        after={"code": role.code, "name": role.name},
        request=request,
    )
    return role


def update_role(actor: User, role: Role, data: dict, request=None) -> Role:
    if role.is_system and "code" in data:
        raise ConflictError("SYSTEM_ROLE_LOCKED", "System roles cannot change their code.")
    before = {"name": role.name, "description": role.description, "branch_scope": role.branch_scope}
    for field in ("name", "description", "branch_scope"):
        if field in data and data[field] is not None:
            setattr(role, field, data[field])
    role.save()
    log_action(
        actor=actor,
        action="role_updated",
        entity_type="Role",
        entity_id=role.id,
        before=before,
        after={"name": role.name, "description": role.description, "branch_scope": role.branch_scope},
        request=request,
    )
    return role
