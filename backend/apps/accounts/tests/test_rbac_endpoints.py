"""Endpoint-level RBAC checks: search scoping, permission catalog access, attachments."""

from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.helpers import grant_role

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_search_only_includes_permitted_modules(actor, medicine, customer):
    grant_role(actor, ["MEDICINE_VIEW"])

    response = _client(actor).get("/api/v1/search/?q=Par")

    assert response.status_code == 200
    assert set(response.json()["results"].keys()) == {"medicines"}


def test_search_includes_multiple_permitted_modules(actor, medicine, customer):
    grant_role(actor, ["MEDICINE_VIEW", "CUSTOMER_VIEW"])

    response = _client(actor).get("/api/v1/search/?q=Par")

    assert set(response.json()["results"].keys()) == {"medicines", "customers"}


def test_permissions_catalog_allows_role_manage_without_role_view(actor):
    grant_role(actor, ["ROLE_MANAGE"], module="identity")

    response = _client(actor).get("/api/v1/permissions/")

    assert response.status_code == 200
    assert "identity" in response.json()


def test_permissions_catalog_denied_without_role_permissions(actor):
    grant_role(actor, ["USER_VIEW"])

    response = _client(actor).get("/api/v1/permissions/")

    assert response.status_code == 403


def test_attachment_unknown_owner_type_denied(actor):
    grant_role(actor, ["STOCK_ADJUST"])

    response = _client(actor).post(
        "/api/v1/attachments/", {"owner_type": "UNKNOWN", "owner_id": str(uuid4())}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
