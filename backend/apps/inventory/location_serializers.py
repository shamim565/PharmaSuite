from rest_framework import serializers

from apps.inventory.models import WarehouseLocation


class WarehouseLocationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = WarehouseLocation
        fields = [
            "id",
            "branch",
            "branch_name",
            "zone",
            "rack",
            "bin",
            "label",
            "is_active",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "label", "created_at"]
