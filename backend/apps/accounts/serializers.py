from rest_framework import serializers

from apps.accounts.models import Permission, Role, User
from apps.branches.models import Branch


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "module", "action", "label", "is_sensitive"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system", "branch_scope"]


class RoleDetailSerializer(RoleSerializer):
    permissions = serializers.SerializerMethodField()

    def get_permissions(self, obj):
        return [
            {
                "code": rp.permission.code,
                "module": rp.permission.module,
                "label": rp.permission.label,
                "effect": rp.effect,
            }
            for rp in obj.role_permissions.select_related("permission").order_by(
                "permission__module", "permission__code"
            )
        ]


class RoleCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(regex=r"^[A-Z][A-Z0-9_]{2,49}$")
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    branch_scope = serializers.ChoiceField(choices=["ALL", "ASSIGNED"], default="ASSIGNED")


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    branch_scope = serializers.ChoiceField(choices=["ALL", "ASSIGNED"], required=False)


class RolePermissionEntrySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    effect = serializers.ChoiceField(choices=["ALLOW", "DENY"], default="ALLOW")


class RolePermissionsWriteSerializer(serializers.Serializer):
    permissions = RolePermissionEntrySerializer(many=True)


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "mobile",
            "email",
            "is_superuser",
            "must_change_password",
            "default_branch_id",
            "totp_enabled",
            "roles",
            "branches",
            "permissions",
        ]

    def get_roles(self, obj):
        return [
            {"id": ur.role.id, "code": ur.role.code, "name": ur.role.name}
            for ur in obj.user_roles.select_related("role").all()
        ]

    def get_branches(self, obj):
        return [
            {
                "id": ub.branch_id,
                "code": ub.branch.code,
                "name": ub.branch.name,
                "is_default": ub.is_default,
            }
            for ub in obj.user_branches.select_related("branch").all()
        ]

    def get_permissions(self, obj):
        return sorted(obj.effective_permission_codes)


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "mobile",
            "email",
            "status",
            "is_superuser",
            "totp_enabled",
            "default_branch_id",
            "last_login_at",
            "created_at",
            "roles",
            "branches",
        ]

    def get_roles(self, obj):
        return [
            {"id": ur.role.id, "code": ur.role.code, "name": ur.role.name}
            for ur in obj.user_roles.select_related("role").all()
        ]

    def get_branches(self, obj):
        return [
            {
                "id": ub.branch_id,
                "code": ub.branch.code,
                "name": ub.branch.name,
                "is_default": ub.is_default,
            }
            for ub in obj.user_branches.select_related("branch").all()
        ]


class UserCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    mobile = serializers.RegexField(regex=r"^[0-9+\- ]{6,20}$")
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    role_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    default_branch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_role_ids(self, value):
        if not value:
            return value
        found = set(Role.objects.filter(id__in=value).values_list("id", flat=True))
        missing = set(value) - {str(f) for f in found} if found else set(value)
        missing = {m for m in missing if m not in found and str(m) not in {str(f) for f in found}}
        if missing:
            raise serializers.ValidationError("One or more roles do not exist.")
        return value

    def validate_branch_ids(self, value):
        if not value:
            return value
        found = set(Branch.objects.filter(id__in=value).values_list("id", flat=True))
        missing = [m for m in value if m not in found]
        if missing:
            raise serializers.ValidationError("One or more branches do not exist.")
        return value

    def validate(self, attrs):
        default_branch = attrs.get("default_branch_id")
        branch_ids = attrs.get("branch_ids") or []
        if default_branch and branch_ids and default_branch not in branch_ids:
            raise serializers.ValidationError(
                {"default_branch_id": "Default branch must be one of the assigned branches."}
            )
        return attrs


class UserUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["PENDING_ACTIVATION", "ACTIVE", "DEACTIVATED"], required=False
    )
    role_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    default_branch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_role_ids(self, value):
        found = {str(f) for f in Role.objects.filter(id__in=value).values_list("id", flat=True)}
        missing = {str(m) for m in value} - found
        if missing:
            raise serializers.ValidationError("One or more roles do not exist.")
        return value

    def validate_branch_ids(self, value):
        found = {str(f) for f in Branch.objects.filter(id__in=value).values_list("id", flat=True)}
        missing = {str(m) for m in value} - found
        if missing:
            raise serializers.ValidationError("One or more branches do not exist.")
        return value

    def validate(self, attrs):
        default_branch = attrs.get("default_branch_id")
        branch_ids = attrs.get("branch_ids")
        if default_branch and branch_ids is not None and default_branch not in branch_ids:
            raise serializers.ValidationError(
                {"default_branch_id": "Default branch must be one of the assigned branches."}
            )
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True)
