import pytest
from fastapi.testclient import TestClient

from tests.tenancy_helpers import API, add_member, create_org, login, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")


def _setup(client: TestClient) -> tuple[dict[str, str], dict[str, str], str]:
    owner, admin = login(client, "owner"), login(client, "admin")
    org = create_org(client, owner)
    add_member(org["id"], "admin", "admin")
    return owner, admin, org["id"]


def _roles_url(org_id: str) -> str:
    return f"{API}/organizations/{org_id}/roles"


def test_roles_are_listed_paginated_and_sortable(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    page = client.get(f"{_roles_url(org)}?page_size=2&sort=-name", headers=owner).json()
    assert (page["total"], page["pages"], len(page["items"])) == (4, 2, 2)
    assert [r["name"] for r in page["items"]] == ["Viewer", "Owner"]
    assert client.get(f"{_roles_url(org)}?sort=secret", headers=owner).status_code == 400


def test_owner_can_create_a_custom_role_with_a_wildcard(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    body = {
        "name": "Auditor",
        "description": "Reads everything",
        "permissions": ["members:read", "roles:*"],
    }
    response = client.post(_roles_url(org), json=body, headers=owner)
    assert response.status_code == 201
    role = response.json()
    assert role["is_system"] is False and role["key"] is None
    assert role["permissions"] == ["members:read", "roles:*"]


def test_unknown_or_malformed_permissions_are_rejected(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    for bad in (["invoices:create"], ["Not A Permission"], ["members:*", "typo:*"]):
        response = client.post(
            _roles_url(org), json={"name": "Bad", "permissions": bad}, headers=owner
        )
        assert response.status_code == 400, bad
        assert response.json()["error"]["code"] == "invalid_permissions"


def test_role_names_are_unique_ignoring_case(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    response = client.post(
        _roles_url(org), json={"name": "ADMIN", "permissions": []}, headers=owner
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "role_name_taken"


def test_you_cannot_grant_what_you_do_not_hold(billing_client: TestClient) -> None:
    owner, admin = login(billing_client, "owner"), login(billing_client, "admin")
    org = create_org(billing_client, owner)["id"]
    add_member(org, "admin", "admin")
    url = _roles_url(org)
    ok = billing_client.post(url, json={"name": "Ok", "permissions": ["members:*"]}, headers=admin)
    assert ok.status_code == 201
    # Admins hold no billing permission, so they cannot hand it out.
    denied = billing_client.post(
        url, json={"name": "Money", "permissions": ["billing:manage"]}, headers=admin
    )
    assert denied.status_code == 403
    assert "do not hold" in denied.json()["error"]["message"]
    assert (
        billing_client.post(
            url, json={"name": "Money", "permissions": ["billing:manage"]}, headers=owner
        ).status_code
        == 201
    )


def test_viewers_cannot_manage_roles(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    login(client, "vera")
    add_member(org, "vera", "viewer")
    vera = login(client, "vera")
    assert (
        client.post(
            _roles_url(org), json={"name": "X", "permissions": []}, headers=vera
        ).status_code
        == 403
    )
    assert (
        client.get(_roles_url(org), headers=vera).status_code == 403
    )  # viewers lack roles:read too
    assert client.get(_roles_url(org), headers=owner).status_code == 200


def test_owner_role_is_locked_and_starter_roles_cannot_be_renamed_or_deleted(
    client: TestClient,
) -> None:
    owner, _admin, org = _setup(client)
    roles = roles_by_key(client, owner, org)
    owner_role = f"{_roles_url(org)}/{roles['owner']['id']}"
    assert client.patch(owner_role, json={"description": "x"}, headers=owner).status_code == 409
    assert client.delete(owner_role, headers=owner).status_code == 409
    member_role = f"{_roles_url(org)}/{roles['member']['id']}"
    assert client.patch(member_role, json={"name": "Renamed"}, headers=owner).status_code == 409
    assert client.delete(member_role, headers=owner).status_code == 409
    # But a starter role's permissions can be tuned.
    tuned = client.patch(member_role, json={"permissions": ["organization:read"]}, headers=owner)
    assert tuned.status_code == 200 and tuned.json()["permissions"] == ["organization:read"]


def test_custom_role_can_be_edited_and_deleted_unless_in_use(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    created = client.post(
        _roles_url(org), json={"name": "Temp", "permissions": []}, headers=owner
    ).json()
    url = f"{_roles_url(org)}/{created['id']}"
    edited = client.patch(
        url, json={"name": "Temp 2", "permissions": ["members:read"]}, headers=owner
    )
    assert edited.json()["name"] == "Temp 2"
    login(client, "carl")
    member_id = add_member(org, "carl", "viewer")
    client.patch(
        f"{API}/organizations/{org}/members/{member_id}",
        json={"role_id": created["id"]},
        headers=owner,
    )
    blocked = client.delete(url, headers=owner)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "role_in_use"
    viewer = roles_by_key(client, owner, org)["viewer"]["id"]
    client.patch(
        f"{API}/organizations/{org}/members/{member_id}", json={"role_id": viewer}, headers=owner
    )
    assert client.delete(url, headers=owner).status_code == 204
    assert client.delete(url, headers=owner).status_code == 404


def test_admin_cannot_edit_a_role_more_powerful_than_their_own(billing_client: TestClient) -> None:
    owner, admin = login(billing_client, "owner"), login(billing_client, "admin")
    org = create_org(billing_client, owner)["id"]
    add_member(org, "admin", "admin")
    accountant = roles_by_key(billing_client, owner, org)["accountant"]
    url = f"{_roles_url(org)}/{accountant['id']}"
    assert (
        billing_client.patch(
            url, json={"permissions": ["organization:read"]}, headers=admin
        ).status_code
        == 403
    )
    # Starter roles cannot be deleted at all; the escalation rule is tested on a custom role below.
    assert billing_client.delete(url, headers=admin).status_code == 409
    assert (
        billing_client.patch(
            url, json={"permissions": ["organization:read"]}, headers=owner
        ).status_code
        == 200
    )


def test_only_the_owner_role_may_hold_every_permission(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    created = client.post(
        _roles_url(org), json={"name": "Boss", "permissions": ["*"]}, headers=owner
    )
    assert created.status_code == 400 and created.json()["error"]["code"] == "invalid_permissions"
    member = roles_by_key(client, owner, org)["member"]["id"]
    tuned = client.patch(f"{_roles_url(org)}/{member}", json={"permissions": ["*"]}, headers=owner)
    assert tuned.status_code == 400


def test_custom_roles_can_be_renamed_but_not_to_an_existing_name(client: TestClient) -> None:
    owner, _admin, org = _setup(client)
    first = client.post(
        _roles_url(org), json={"name": "Alpha", "permissions": []}, headers=owner
    ).json()
    client.post(_roles_url(org), json={"name": "Beta", "permissions": []}, headers=owner)
    url = f"{_roles_url(org)}/{first['id']}"
    clash = client.patch(url, json={"name": "beta"}, headers=owner)
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "role_name_taken"
    renamed = client.patch(url, json={"name": "Gamma", "description": "Third"}, headers=owner)
    assert (renamed.json()["name"], renamed.json()["description"]) == ("Gamma", "Third")


def test_admin_cannot_edit_or_delete_a_custom_role_more_powerful_than_their_own(
    billing_client: TestClient,
) -> None:
    owner, admin = login(billing_client, "owner"), login(billing_client, "admin")
    org = create_org(billing_client, owner)["id"]
    add_member(org, "admin", "admin")
    money = billing_client.post(
        _roles_url(org), json={"name": "Money", "permissions": ["billing:manage"]}, headers=owner
    ).json()
    url = f"{_roles_url(org)}/{money['id']}"
    assert billing_client.patch(url, json={"description": "x"}, headers=admin).status_code == 403
    assert billing_client.delete(url, headers=admin).status_code == 403
    assert billing_client.delete(url, headers=owner).status_code == 204
