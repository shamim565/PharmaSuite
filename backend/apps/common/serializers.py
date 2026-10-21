"""Serializers for ad-hoc endpoints that return hand-built dictionaries."""

from rest_framework import serializers


class NotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    deep_link = serializers.CharField()
    payload = serializers.JSONField()
    is_read = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class FiscalPeriodSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    fiscal_year = serializers.IntegerField()
    period_month = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.CharField()
    locked_by_name = serializers.CharField()
    locked_at = serializers.DateTimeField(allow_null=True)
    lock_reason = serializers.CharField()
    unlock_by_name = serializers.CharField()
    unlock_reason = serializers.CharField()
