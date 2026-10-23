"""Per-device session tracking, rotation and revocation."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts import services
from apps.accounts.models import UserSession

pytestmark = pytest.mark.django_db


def _login(user):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {"identifier": user.mobile, "password": "Test@1234"},
        format="json",
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    return client, response


def test_login_creates_session_and_sid_claim(actor):
    _, response = _login(actor)
    session = UserSession.objects.get(user=actor)
    assert session.revoked_at is None
    assert AccessToken(response.json()["access"])["sid"] == str(session.sid)


def test_refresh_keeps_session_and_updates_last_seen(actor):
    client, _ = _login(actor)
    session = UserSession.objects.get(user=actor)
    before = session.last_seen_at

    response = client.post("/api/v1/auth/refresh/")

    assert response.status_code == 200, response.content
    session.refresh_from_db()
    assert session.revoked_at is None
    assert session.last_seen_at >= before
    assert AccessToken(response.json()["access"])["sid"] == str(session.sid)
    assert UserSession.objects.filter(user=actor).count() == 1


def test_revoked_session_cannot_refresh(actor):
    client, _ = _login(actor)
    session = UserSession.objects.get(user=actor)
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at", "updated_at"])

    response = client.post("/api/v1/auth/refresh/")

    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


def test_session_list_marks_current_device(actor):
    client, _ = _login(actor)

    response = client.get("/api/v1/auth/sessions/")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["current"] is True


def test_revoke_other_users_session_is_not_found(actor, approver):
    client, _ = _login(actor)
    other = UserSession.objects.create(user=approver)

    response = client.delete(f"/api/v1/auth/sessions/{other.sid}/")

    assert response.status_code == 404


def test_revoke_all_keeps_current_session(actor):
    client, _ = _login(actor)
    current = UserSession.objects.get(user=actor)
    UserSession.objects.create(user=actor, user_agent="other device")

    response = client.post("/api/v1/auth/sessions/revoke-all/")

    assert response.status_code == 200
    assert response.json()["revoked"] == 1
    current.refresh_from_db()
    assert current.revoked_at is None
    assert UserSession.objects.filter(user=actor, revoked_at__isnull=True).count() == 1


def test_logout_revokes_current_session(actor):
    client, _ = _login(actor)

    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == 204
    assert UserSession.objects.filter(user=actor, revoked_at__isnull=True).count() == 0


def test_password_change_revokes_all_sessions(actor):
    _login(actor)
    assert UserSession.objects.filter(user=actor, revoked_at__isnull=True).count() == 1

    services.change_password(actor, "NewPass@1234")

    assert UserSession.objects.filter(user=actor, revoked_at__isnull=True).count() == 0
