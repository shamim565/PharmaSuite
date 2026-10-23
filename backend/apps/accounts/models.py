import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class UserStatus(models.TextChoices):
    PENDING_ACTIVATION = "PENDING_ACTIVATION", "Pending activation"
    ACTIVE = "ACTIVE", "Active"
    DEACTIVATED = "DEACTIVATED", "Deactivated"


class BranchScope(models.TextChoices):
    ALL = "ALL", "All branches"
    ASSIGNED = "ASSIGNED", "Assigned branches"


class PermissionEffect(models.TextChoices):
    ALLOW = "ALLOW", "Allow"
    DENY = "DENY", "Deny"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, mobile: str, password: str | None, **extra):
        if not mobile:
            raise ValueError("Mobile number is required")
        user = self.model(mobile=mobile, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, mobile: str, password: str | None = None, **extra):
        extra.setdefault("status", UserStatus.ACTIVE)
        return self._create_user(mobile, password, **extra)

    def create_superuser(self, mobile: str, password: str | None = None, **extra):
        extra.setdefault("is_superuser", True)
        extra.setdefault("status", UserStatus.ACTIVE)
        return self._create_user(mobile, password, **extra)


class User(AbstractBaseUser, BaseModel):
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=UserStatus.choices, default=UserStatus.ACTIVE)
    must_change_password = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_enabled = models.BooleanField(default=False)
    default_branch = models.ForeignKey(
        "branches.Branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_users",
    )
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    self_reset_disabled = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    _permission_cache: set[str] | None = None

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mobile})"

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def effective_permission_codes(self) -> set[str]:
        if self._permission_cache is not None:
            return self._permission_cache

        if self.is_superuser:
            codes = set(Permission.objects.values_list("code", flat=True))
        else:
            rows = (
                RolePermission.objects.filter(role__user_roles__user=self)
                .values_list("permission__code", "effect")
            )
            allow: set[str] = set()
            deny: set[str] = set()
            for code, effect in rows:
                (deny if effect == PermissionEffect.DENY else allow).add(code)
            codes = allow - deny

        self._permission_cache = codes
        return codes

    @property
    def has_all_branch_scope(self) -> bool:
        if self.is_superuser:
            return True
        return self.user_roles.filter(role__branch_scope=BranchScope.ALL).exists()

    @property
    def branch_ids(self) -> list:
        return list(self.user_branches.values_list("branch_id", flat=True))


class Role(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    branch_scope = models.CharField(
        max_length=10, choices=BranchScope.choices, default=BranchScope.ASSIGNED
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Permission(BaseModel):
    code = models.CharField(max_length=80, unique=True)
    module = models.CharField(max_length=40, db_index=True)
    action = models.CharField(max_length=30)
    label = models.CharField(max_length=120)
    is_sensitive = models.BooleanField(default=False)

    class Meta:
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return self.code


class RolePermission(BaseModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )
    effect = models.CharField(
        max_length=10, choices=PermissionEffect.choices, default=PermissionEffect.ALLOW
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission")
        ]


class UserRole(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="uq_user_role")]


class UserBranch(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_branches")
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.CASCADE, related_name="user_branches"
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "branch"], name="uq_user_branch")
        ]


class LoginAttempt(BaseModel):
    identifier = models.CharField(max_length=254, db_index=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_attempts"
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=60, blank=True)


class PasswordHistory(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_history")
    password_hash = models.CharField(max_length=300)


class UserSession(BaseModel):
    """A signed-in device/client. The refresh token carries the ``sid`` claim."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    sid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user_agent = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self) -> str:
        return f"{self.user_id} {self.sid}"
