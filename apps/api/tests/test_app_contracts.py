"""Rules about the app as a whole, checked by BEHAVIOUR through public interfaces.

(An earlier version walked FastAPI's internal route table and silently checked nothing after an
upgrade. These tests list routes from the public OpenAPI schema and actually call them.)
"""

import re
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tenancy_helpers import API, create_org, login

pytestmark = pytest.mark.usefixtures("clean_db")
APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Routes under /api/v1 intentionally open to ANY signed-in user (no organization role needed).
# Adding to this set is a deliberate security decision: justify it in the review.
AUTHENTICATED_ONLY = {
    ("get", "/api/v1/me"),  # your own profile and organizations
    ("get", "/api/v1/permissions"),  # the product's permission catalog (not tenant data)
    ("post", "/api/v1/organizations"),  # anyone may create their own organization
    ("post", "/api/v1/invitations/accept"),  # protected by the secret token + matching email
    # Anyone may leave an organization; the service checks members:manage when removing others.
    ("delete", "/api/v1/organizations/{org_id}/members/{membership_id}"),
}


def _api_operations(app: FastAPI) -> list[tuple[str, str]]:
    paths = app.openapi()["paths"]
    return [
        (method, path)
        for path, item in paths.items()
        if path.startswith("/api/v1")
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    ]


def _fill(path: str, org_id: str) -> str:
    filled = path.replace("{org_id}", org_id)
    return re.sub(r"\{[^}]+\}", lambda _m: str(uuid.uuid4()), filled)


def test_the_contract_tests_really_see_the_api(app: FastAPI) -> None:
    """Guard against vacuous passes: if routing internals change, this fails loudly."""
    operations = _api_operations(app)
    assert len(operations) >= 15
    assert ("get", "/api/v1/organizations/{org_id}/members") in operations


def test_every_api_route_rejects_anonymous_callers(client: TestClient, app: FastAPI) -> None:
    org = str(uuid.uuid4())
    leaks = []
    for method, path in _api_operations(app):
        response = client.request(method, _fill(path, org), json={})
        if response.status_code != 401:
            leaks.append(f"{method.upper()} {path} answered {response.status_code} without a login")
    assert leaks == []


def test_every_organization_route_demands_a_permission(client: TestClient, app: FastAPI) -> None:
    """A member whose role grants NOTHING is refused everywhere, unless deliberately allowed."""
    owner, nobody = login(client, "owner"), login(client, "nobody", "nobody@example.com")
    org = create_org(client, owner)["id"]
    role = client.post(
        f"{API}/organizations/{org}/roles",
        json={"name": "Nothing", "permissions": []},
        headers=owner,
    ).json()["id"]
    invite = client.post(
        f"{API}/organizations/{org}/invitations",
        json={"email": "nobody@example.com", "role_id": role},
        headers=owner,
    ).json()
    accepted = client.post(
        f"{API}/invitations/accept", json={"token": invite["token"]}, headers=nobody
    )
    assert accepted.status_code == 200

    problems = []
    for method, path in _api_operations(app):
        if (method, path) in AUTHENTICATED_ONLY:
            continue
        if "{org_id}" not in path:
            problems.append(
                f"{method.upper()} {path}: not organization-scoped and not on the allow-list"
            )
            continue
        response = client.request(method, _fill(path, org), json={}, headers=nobody)
        if response.status_code != 403:
            problems.append(
                f"{method.upper()} {path}: a member with no permissions got {response.status_code}"
            )
    assert problems == []


def test_the_database_session_is_only_ever_used_through_sessiondep() -> None:
    """SessionDep finishes the transaction BEFORE the response is sent (see core/db/session.py)."""
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if path.name != "session.py" and "Depends(get_session" in path.read_text()
    ]
    assert offenders == []
