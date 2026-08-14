"""Notification preferences gate task notifications."""

import pytest
from rest_framework.test import APIClient

from apps.common.models import Notification, NotificationPreference
from apps.common.notifications import notify

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_notify_respects_category_preference(actor):
    assert notify(actor, "LOW_STOCK", "Low stock", category="STOCK") is not None

    NotificationPreference.objects.create(user=actor, category="STOCK", enabled=False)

    assert notify(actor, "LOW_STOCK", "Another", category="STOCK") is None
    # Other categories are unaffected.
    assert notify(actor, "NEAR_EXPIRY", "Near expiry", category="EXPIRY") is not None
    assert Notification.objects.filter(user=actor).count() == 2


def test_notify_without_category_always_creates(actor):
    assert notify(actor, "GENERIC", "Hello") is not None


def test_preferences_api_roundtrip(actor):
    response = _client(actor).get("/api/v1/notifications/preferences/")
    assert response.status_code == 200
    rows = response.json()["results"]
    assert {row["category"] for row in rows} == {
        "STOCK",
        "EXPIRY",
        "DUES",
        "APPROVALS",
        "VISITS",
    }
    assert all(row["enabled"] for row in rows)

    updated = _client(actor).put(
        "/api/v1/notifications/preferences/",
        {"preferences": {"STOCK": False, "VISITS": False}},
        format="json",
    )
    assert updated.status_code == 200
    state = {row["category"]: row["enabled"] for row in updated.json()["results"]}
    assert state["STOCK"] is False
    assert state["VISITS"] is False
    assert state["DUES"] is True


def test_preferences_api_rejects_unknown_category(actor):
    response = _client(actor).put(
        "/api/v1/notifications/preferences/",
        {"preferences": {"NONSENSE": True}},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "UNKNOWN_CATEGORY"
