import uuid

import pytest
from fastapi.testclient import TestClient

from tests.auth_helpers import auth_header, make_token
from tests.tenancy_helpers import API, add_member, create_org, login, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")


def test_new_user_belongs_to_no_organizations(client: TestClient) -> None:
    headers = login(client, "alice")
    body = client.get(f"{API}/me", headers=headers).json()
    assert body["email"] == "alice@example.com"
    assert body["organizations"] == []


def test_creator_becomes_owner_and_starter_roles_are_copied(client: TestClient) -> None:
    headers = login(client, "alice")
    org = create_org(client, headers, "Acme Pharmacy")
    assert org["slug"] == "acme-pharmacy"
    roles = roles_by_key(client, headers, org["id"])
    assert set(roles) == {"owner", "admin", "member", "viewer"}
    assert roles["owner"]["permissions"] == ["*"]
    assert all(role["is_system"] for role in roles.values())
    me = client.get(f"{API}/me", headers=headers).json()
    assert [(o["name"], o["role"]["key"]) for o in me["organizations"]] == [
        ("Acme Pharmacy", "owner")
    ]


def test_slug_collisions_get_a_unique_suffix_and_custom_slugs_are_validated(
    client: TestClient,
) -> None:
    alice, bob = login(client, "alice"), login(client, "bob")
    first = create_org(client, alice, "Same Name")
    second = create_org(client, bob, "Same Name")
    assert first["slug"] == "same-name"
    assert second["slug"].startswith("same-name-") and second["slug"] != first["slug"]
    custom = client.post(
        f"{API}/organizations", json={"name": "Foo", "slug": "my-org"}, headers=alice
    )
    assert custom.json()["slug"] == "my-org"
    for bad in ("A", "UPPER", "has space", "-lead", "x" * 60):
        response = client.post(
            f"{API}/organizations", json={"name": "Foo", "slug": bad}, headers=alice
        )
        assert response.status_code == 422, bad


@pytest.mark.parametrize("name", ["", " ", "x", "y" * 81])
def test_organization_name_is_validated(client: TestClient, name: str) -> None:
    response = client.post(
        f"{API}/organizations", json={"name": name}, headers=login(client, "alice")
    )
    assert response.status_code == 422


def test_creating_an_organization_requires_login(client: TestClient) -> None:
    assert client.post(f"{API}/organizations", json={"name": "Nope"}).status_code == 401


def test_member_can_read_but_outsiders_get_404_not_403(client: TestClient) -> None:
    alice, mallory = login(client, "alice"), login(client, "mallory")
    org = create_org(client, alice)
    assert (
        client.get(f"{API}/organizations/{org['id']}", headers=alice).json()["name"] == org["name"]
    )
    outsider = client.get(f"{API}/organizations/{org['id']}", headers=mallory)
    unknown = client.get(f"{API}/organizations/{uuid.uuid4()}", headers=mallory)
    assert outsider.status_code == unknown.status_code == 404
    assert (
        outsider.json()["error"]["message"] == unknown.json()["error"]["message"]
    )  # nothing leaks


def test_renaming_requires_the_update_permission(client: TestClient) -> None:
    alice, vera = login(client, "alice"), login(client, "vera")
    org = create_org(client, alice)
    add_member(org["id"], "vera", "viewer")
    denied = client.patch(f"{API}/organizations/{org['id']}", json={"name": "Hacked"}, headers=vera)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
    ok = client.patch(
        f"{API}/organizations/{org['id']}", json={"name": "Better Name"}, headers=alice
    )
    assert ok.json()["name"] == "Better Name"


def test_permission_catalog_is_available_to_signed_in_users(client: TestClient) -> None:
    assert client.get(f"{API}/permissions").status_code == 401
    names = {
        p["name"] for p in client.get(f"{API}/permissions", headers=login(client, "alice")).json()
    }
    assert {"members:manage", "roles:manage"} <= names


def test_a_malformed_organization_id_is_a_validation_error(client: TestClient) -> None:
    headers = auth_header(make_token("alice"))
    assert client.get(f"{API}/organizations/not-a-uuid", headers=headers).status_code == 422
