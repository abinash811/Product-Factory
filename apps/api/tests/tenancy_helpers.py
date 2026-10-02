"""Shortcuts for tests that exercise organizations through the real API."""

from typing import Any

import psycopg
from fastapi.testclient import TestClient

from tests.auth_helpers import auth_header, make_token
from tests.conftest import TEST_DATABASE_URL

API = "/api/v1"


def login(client: TestClient, sub: str, email: str | None = None) -> dict[str, str]:
    headers = auth_header(make_token(sub, email or f"{sub}@example.com"))
    assert client.get(f"{API}/me", headers=headers).status_code == 200
    return headers


def create_org(
    client: TestClient, headers: dict[str, str], name: str = "Acme Pharmacy"
) -> dict[str, Any]:
    response = client.post(f"{API}/organizations", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def roles_by_key(
    client: TestClient, headers: dict[str, str], org_id: str
) -> dict[str, dict[str, Any]]:
    response = client.get(f"{API}/organizations/{org_id}/roles?page_size=100", headers=headers)
    assert response.status_code == 200, response.text
    return {role["key"] or role["name"]: role for role in response.json()["items"]}


def add_member(org_id: str, sub: str, role_key: str) -> str:
    """Put an existing user into an organization straight in the database (no invitations yet)."""
    plain_url = TEST_DATABASE_URL.replace("+psycopg", "")
    with psycopg.connect(plain_url, autocommit=True) as connection:
        row = connection.execute(
            "INSERT INTO memberships (organization_id, user_id, role_id) "
            "SELECT %s, u.id, r.id FROM users u, roles r "
            "WHERE u.auth_subject = %s AND r.organization_id = %s AND r.key = %s RETURNING id",
            (org_id, sub, org_id, role_key),
        ).fetchone()
    assert row is not None
    return str(row[0])


def members_by_email(
    client: TestClient, headers: dict[str, str], org_id: str
) -> dict[str, dict[str, Any]]:
    response = client.get(f"{API}/organizations/{org_id}/members?page_size=100", headers=headers)
    assert response.status_code == 200, response.text
    return {m["email"]: m for m in response.json()["items"]}
