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
    PermissionEffect,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
    UserSession,
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


def create_session(user: User, request=None) -> UserSession:
    """Register a device/client session for a successful login."""
    meta = client_meta(request)
    return UserSession.objects.create(
        user=user,
        ip=meta.get("ip") or None,
        user_agent=meta.get("user_agent", ""),
    )


def issue_tokens(user: User, session: UserSession | None = None) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    if session is not None:
        refresh["sid"] = str(session.sid)
    return str(refresh.access_token), str(refresh)


def revoke_session(session: UserSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at", "updated_at"])


def revoke_all_sessions(user: User) -> int:
    UserSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
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
        payload = None
        try:
            payload = UntypedToken(raw_token)
            user = User.objects.filter(id=payload.get("user_id")).first()
        except TokenError:
            payload = None
        if user is not None:
            sid = payload.get("sid") if payload is not None else None
            if sid:
                session = UserSession.objects.filter(user=user, sid=sid).first()
                if session is not None:
                    revoke_session(session)
            else:
                revoke_all_sessions(user)
            log_action(
                actor=None,
                action="refresh_reuse_detected",
                entity_type="User",
                entity_id=user.id,
                request=request,
                after={"reason": str(exc), "sid": str(sid) if sid else None},
            )
        raise APIError(
            "INVALID_REFRESH_TOKEN",
            "Session expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc

    user = User.objects.filter(id=refresh.get("user_id")).first()
    if user is None or user.status != UserStatus.ACTIVE:
        raise APIError("INVALID_REFRESH_TOKEN", "Session expired. Please sign in again.", status.HTTP_401_UNAUTHORIZED)

    sid = refresh.get("sid")
    if sid:
        session = UserSession.objects.filter(
            user=user, sid=sid, revoked_at__isnull=True
        ).first()
        if session is None:
            raise APIError(
                "SESSION_REVOKED",
                "This session has been revoked. Please sign in again.",
                status.HTTP_401_UNAUTHORIZED,
            )
    else:
        # Legacy token issued before session tracking: upgrade it on first refresh.
        session = create_session(user, request)

    session.last_seen_at = timezone.now()
    meta = client_meta(request)
    session.ip = meta.get("ip") or session.ip
    session.user_agent = meta.get("user_agent") or session.user_agent
    session.save(update_fields=["last_seen_at", "ip", "user_agent", "updated_at"])

    access = str(refresh.access_token)
    refresh.blacklist()
    new_refresh = RefreshToken.for_user(user)
    new_refresh["sid"] = str(session.sid)
    return user, access, str(new_refresh)


# --------------------------------------------------------------------------- 2FA (TOTP)


def generate_totp_secret(user: User) -> str:
    import pyotp

    if user.totp_enabled:
        raise APIError(
            "TOTP_ALREADY_ENABLED", "Two-factor authentication is already enabled.",
            status.HTTP_400_BAD_REQUEST,
        )
    user.totp_secret = pyotp.random_base32()
    user.save(update_fields=["totp_secret", "updated_at"])
    return user.totp_secret


def totp_provisioning_uri(user: User) -> str:
    import pyotp

    if not user.totp_secret:
        raise APIError(
            "TOTP_NOT_SETUP", "Two-factor authentication is not set up.",
            status.HTTP_400_BAD_REQUEST,
        )
    return pyotp.TOTP(user.totp_secret).provisioning_uri(
        name=user.mobile, issuer_name=settings.TOTP_ISSUER
    )


def verify_totp_code(user: User, code: str) -> bool:
    import pyotp

    if not user.totp_secret or not code:
        return False
    return bool(pyotp.TOTP(user.totp_secret).verify(str(code).strip(), valid_window=1))


def enable_totp(user: User, code: str, request=None) -> User:
    if not user.totp_secret:
        raise APIError(
            "TOTP_NOT_SETUP", "Request a setup secret first.", status.HTTP_400_BAD_REQUEST
        )
    if not verify_totp_code(user, code):
        raise APIError("INVALID_TOTP", "Invalid authentication code.", status.HTTP_400_BAD_REQUEST)
    user.totp_enabled = True
    user.save(update_fields=["totp_enabled", "updated_at"])
    log_action(
        actor=user, action="totp_enabled", entity_type="User", entity_id=user.id, request=request
    )
    return user


def disable_totp(user: User, code: str, request=None) -> User:
    if not user.totp_enabled:
        raise APIError(
            "TOTP_NOT_ENABLED", "Two-factor authentication is not enabled.",
            status.HTTP_400_BAD_REQUEST,
        )
    if not verify_totp_code(user, code):
        raise APIError("INVALID_TOTP", "Invalid authentication code.", status.HTTP_400_BAD_REQUEST)
    user.totp_enabled = False
    user.totp_secret = ""
    user.save(update_fields=["totp_enabled", "totp_secret", "updated_at"])
    log_action(
        actor=user, action="totp_disabled", entity_type="User", entity_id=user.id, request=request
    )
    return user


def reset_totp(actor: User, target: User, request=None) -> User:
    """Admin-side 2FA reset (e.g. lost device)."""
    _ensure_actor_can_manage_target(actor, target)
    target.totp_enabled = False
    target.totp_secret = ""
    target.save(update_fields=["totp_enabled", "totp_secret", "updated_at"])
    revoke_all_sessions(target)
    log_action(
        actor=actor, action="totp_reset", entity_type="User", entity_id=target.id, request=request
    )
    return target


def issue_mfa_token(user: User) -> str:
    from rest_framework_simplejwt.tokens import AccessToken

    token = AccessToken()
    token["user_id"] = str(user.id)
    token["mfa"] = True
    return str(token)


def complete_mfa_login(mfa_token: str, code: str) -> User:
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        payload = AccessToken(mfa_token)
    except TokenError as exc:
        raise APIError(
            "INVALID_MFA_TOKEN",
            "Two-factor session expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if not payload.get("mfa"):
        raise APIError(
            "INVALID_MFA_TOKEN", "Invalid two-factor token.", status.HTTP_401_UNAUTHORIZED
        )
    user = User.objects.filter(id=payload.get("user_id")).first()
    if user is None or user.status != UserStatus.ACTIVE or not user.totp_enabled:
        raise APIError(
            "INVALID_MFA_TOKEN", "Two-factor session expired.", status.HTTP_401_UNAUTHORIZED
        )
    if not verify_totp_code(user, code):
        raise APIError("INVALID_TOTP", "Invalid authentication code.", status.HTTP_400_BAD_REQUEST)
    return user


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


def _permission_codes_for_roles(role_ids) -> set[str]:
    return set(
        RolePermission.objects.filter(
            role_id__in=role_ids, effect=PermissionEffect.ALLOW
        ).values_list("permission__code", flat=True)
    )


def _ensure_actor_can_grant(actor: User, codes: set[str]) -> None:
    """Non-superusers may only grant permissions they themselves hold."""
    if actor.is_superuser or not codes:
        return
    missing = codes - actor.effective_permission_codes
    if missing:
        raise APIError(
            "PRIVILEGE_ESCALATION",
            "You cannot grant permissions you do not hold: " + ", ".join(sorted(missing)),
            status_code=403,
        )


def _ensure_actor_can_edit_role(actor: User, role: Role) -> None:
    """Non-superusers may not edit roles holding permissions they lack."""
    if actor.is_superuser:
        return
    missing = _permission_codes_for_roles([role.id]) - actor.effective_permission_codes
    if missing:
        raise APIError(
            "ROLE_MORE_PRIVILEGED",
            "You cannot edit a role that holds permissions you do not hold.",
            status_code=403,
        )


def _ensure_actor_can_manage_target(actor: User, target: User) -> None:
    """Non-superusers may not modify users holding permissions they lack."""
    if actor.is_superuser or actor.id == target.id:
        return
    if target.is_superuser:
        raise APIError(
            "TARGET_MORE_PRIVILEGED",
            "Only a superuser can modify a superuser.",
            status_code=403,
        )
    extra = target.effective_permission_codes - actor.effective_permission_codes
    if extra:
        raise APIError(
            "TARGET_MORE_PRIVILEGED",
            "You cannot modify a user holding permissions you do not hold.",
            status_code=403,
        )


def _ensure_actor_can_assign_scope(actor: User, branch_scope: str) -> None:
    if branch_scope == BranchScope.ALL and not (
        actor.is_superuser or actor.has_all_branch_scope
    ):
        raise APIError(
            "PRIVILEGE_ESCALATION",
            "Only users with all-branch scope can grant all-branch access.",
            status_code=403,
        )


def _guard_role_assignment(actor: User, role_ids) -> None:
    if not role_ids:
        return
    roles = list(Role.objects.filter(id__in=role_ids))
    _ensure_actor_can_grant(actor, _permission_codes_for_roles(role_ids))
    if actor.is_superuser or actor.has_all_branch_scope:
        return
    for role in roles:
        if role.branch_scope == BranchScope.ALL:
            raise APIError(
                "PRIVILEGE_ESCALATION",
                f"Only all-branch users can assign the all-branch role {role.code}.",
                status_code=403,
            )


def _guard_branch_assignment(actor: User, branch_ids) -> None:
    if not branch_ids or actor.is_superuser or actor.has_all_branch_scope:
        return
    allowed = {str(branch_id) for branch_id in actor.branch_ids}
    extra = {str(branch_id) for branch_id in branch_ids} - allowed
    if extra:
        raise APIError(
            "BRANCH_SCOPE_EXCEEDED",
            "You cannot assign branches outside your own scope.",
            status_code=403,
        )


def _assign_roles_and_branches(
    actor: User, user: User, role_ids, branch_ids, default_branch_id
) -> None:
    if role_ids is not None:
        _guard_role_assignment(actor, role_ids)
    if branch_ids is not None:
        _guard_branch_assignment(actor, branch_ids)
    if default_branch_id is not None and branch_ids is None:
        if not UserBranch.objects.filter(user=user, branch_id=default_branch_id).exists():
            raise APIError(
                "INVALID_DEFAULT_BRANCH",
                "Default branch must be one of the user's assigned branches.",
            )
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
        actor, user, data.get("role_ids"), data.get("branch_ids"), data.get("default_branch_id")
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
    _ensure_actor_can_manage_target(actor, user)
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
        actor,
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
    _ensure_actor_can_manage_target(actor, user)
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
    _ensure_actor_can_edit_role(actor, role)
    _ensure_actor_can_grant(
        actor,
        {row["code"] for row in permissions if row.get("effect", "ALLOW") == "ALLOW"},
    )
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
    _ensure_actor_can_assign_scope(actor, data.get("branch_scope", BranchScope.ASSIGNED))
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
    _ensure_actor_can_edit_role(actor, role)
    if "branch_scope" in data and data["branch_scope"]:
        _ensure_actor_can_assign_scope(actor, data["branch_scope"])
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
