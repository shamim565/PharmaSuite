"""2FA (TOTP) enrollment, login challenge and admin reset."""

import pyotp
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import BranchScope
from apps.accounts.services import disable_totp, enable_totp, generate_totp_secret
from apps.accounts.tests.helpers import grant_role
from apps.common.exceptions import APIError

pytestmark = pytest.mark.django_db

LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _enable_totp(user):
    secret = generate_totp_secret(user)
    user.refresh_from_db()
    enable_totp(user, pyotp.TOTP(secret).now())
    user.refresh_from_db()
    return secret


@override_settings(CACHES=LOCMEM_CACHE)
def test_setup_enable_login_challenge_and_disable(actor):
    client = _client(actor)

    setup = client.post("/api/v1/auth/me/2fa/setup/", {}, format="json")
    assert setup.status_code == 200
    body = setup.json()
    assert body["secret"]
    assert body["provisioning_uri"].startswith("otpauth://totp/")

    wrong = client.post("/api/v1/auth/me/2fa/enable/", {"code": "000000"}, format="json")
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "INVALID_TOTP"

    code = pyotp.TOTP(body["secret"]).now()
    enabled = client.post("/api/v1/auth/me/2fa/enable/", {"code": code}, format="json")
    assert enabled.status_code == 200
    actor.refresh_from_db()
    assert actor.totp_enabled is True

    # Password alone no longer returns tokens.
    login = APIClient().post(
        "/api/v1/auth/login/",
        {"identifier": actor.mobile, "password": "Test@1234"},
        format="json",
    )
    assert login.status_code == 200
    challenge = login.json()
    assert challenge["mfa_required"] is True
    assert "access" not in challenge

    bad = APIClient().post(
        "/api/v1/auth/login/mfa/",
        {"mfa_token": challenge["mfa_token"], "code": "000000"},
        format="json",
    )
    assert bad.status_code == 400

    good = APIClient().post(
        "/api/v1/auth/login/mfa/",
        {"mfa_token": challenge["mfa_token"], "code": pyotp.TOTP(body["secret"]).now()},
        format="json",
    )
    assert good.status_code == 200
    assert good.json()["access"]
    assert good.json()["user"]["totp_enabled"] is True

    # Disable requires a valid current code.
    with pytest.raises(APIError):
        disable_totp(actor, "000000")
    disabled = client.post(
        "/api/v1/auth/me/2fa/disable/",
        {"code": pyotp.TOTP(body["secret"]).now()},
        format="json",
    )
    assert disabled.status_code == 200
    actor.refresh_from_db()
    assert actor.totp_enabled is False


@override_settings(CACHES=LOCMEM_CACHE)
def test_plain_login_unchanged_without_totp(actor):
    login = APIClient().post(
        "/api/v1/auth/login/",
        {"identifier": actor.mobile, "password": "Test@1234"},
        format="json",
    )
    assert login.status_code == 200
    assert login.json()["access"]
    assert login.json()["user"]["totp_enabled"] is False


def test_admin_can_reset_totp(actor, approver):
    grant_role(actor, ["USER_MANAGE"], branch_scope=BranchScope.ALL)
    _enable_totp(approver)

    response = _client(actor).post(f"/api/v1/users/{approver.id}/reset-2fa/", {}, format="json")

    assert response.status_code == 200
    approver.refresh_from_db()
    assert approver.totp_enabled is False
    assert approver.totp_secret == ""


def test_cannot_reset_more_privileged_user_totp(actor, approver):
    grant_role(actor, ["USER_MANAGE"])
    approver.is_superuser = True
    approver.save(update_fields=["is_superuser"])
    _enable_totp(approver)

    response = _client(actor).post(f"/api/v1/users/{approver.id}/reset-2fa/", {}, format="json")

    assert response.status_code == 403
    assert response.json()["code"] == "TARGET_MORE_PRIVILEGED"
    approver.refresh_from_db()
    assert approver.totp_enabled is True
