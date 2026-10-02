import uuid

import pytest
from fastapi.testclient import TestClient

from tests.tenancy_helpers import API, add_member, create_org, login, members_by_email, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")


class World:
    """An organization with an owner, an admin, a member and a viewer."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.h = {name: login(client, name) for name in ("owner", "admin", "member", "viewer")}
        self.org = create_org(client, self.h["owner"])["id"]
        for name in ("admin", "member", "viewer"):
            add_member(self.org, name, name)
        self.roles = roles_by_key(client, self.h["owner"], self.org)
        self.members = members_by_email(client, self.h["owner"], self.org)

    def url(self, who: str) -> str:
        return f"{API}/organizations/{self.org}/members/{self.members[f'{who}@example.com']['id']}"

    def set_role(self, actor: str, who: str, role_key: str) -> int:
        body = {"role_id": self.roles[role_key]["id"]}
        return int(self.client.patch(self.url(who), json=body, headers=self.h[actor]).status_code)


def test_members_are_listed_with_email_and_role(client: TestClient) -> None:
    w = World(client)
    assert {e: m["role"]["key"] for e, m in w.members.items()} == {
        "owner@example.com": "owner",
        "admin@example.com": "admin",
        "member@example.com": "member",
        "viewer@example.com": "viewer",
    }
    page = client.get(
        f"{API}/organizations/{w.org}/members?sort=-email&page_size=2", headers=w.h["owner"]
    ).json()
    assert [m["email"] for m in page["items"]] == ["viewer@example.com", "owner@example.com"]
    assert page["total"] == 4 and page["pages"] == 2


def test_viewer_cannot_list_members_but_member_can(client: TestClient) -> None:
    w = World(client)
    url = f"{API}/organizations/{w.org}/members"
    assert client.get(url, headers=w.h["viewer"]).status_code == 403
    assert client.get(url, headers=w.h["member"]).status_code == 200


def test_owner_changes_a_role_and_the_response_shows_the_new_role(client: TestClient) -> None:
    w = World(client)
    body = {"role_id": w.roles["admin"]["id"]}
    response = client.patch(w.url("member"), json=body, headers=w.h["owner"])
    assert response.status_code == 200
    assert response.json()["role"]["key"] == "admin"


def test_admin_cannot_promote_anyone_to_owner_or_touch_an_owner(client: TestClient) -> None:
    w = World(client)
    assert w.set_role("admin", "member", "owner") == 403
    assert w.set_role("admin", "owner", "viewer") == 403
    assert client.delete(w.url("owner"), headers=w.h["admin"]).status_code == 403
    assert w.set_role("admin", "member", "viewer") == 200  # normal admin work is fine


def test_member_without_manage_permission_cannot_change_roles_or_remove_others(
    client: TestClient,
) -> None:
    w = World(client)
    assert w.set_role("member", "viewer", "admin") == 403
    assert client.delete(w.url("viewer"), headers=w.h["member"]).status_code == 403


def test_the_last_owner_can_neither_leave_nor_be_demoted(client: TestClient) -> None:
    w = World(client)
    for attempt in (
        client.delete(w.url("owner"), headers=w.h["owner"]),
        client.patch(
            w.url("owner"), json={"role_id": w.roles["admin"]["id"]}, headers=w.h["owner"]
        ),
    ):
        assert attempt.status_code == 409
        assert attempt.json()["error"]["code"] == "last_owner"


def test_with_a_second_owner_an_owner_may_step_down_or_leave(client: TestClient) -> None:
    w = World(client)
    assert w.set_role("owner", "admin", "owner") == 200  # two owners now
    assert w.set_role("owner", "owner", "admin") == 200  # the original owner steps down
    # The promoted admin is now the ONLY owner, so cannot leave...
    assert client.delete(w.url("admin"), headers=w.h["admin"]).status_code == 409
    # ...until someone else is promoted. Then the first owner can leave.
    assert w.set_role("admin", "member", "owner") == 200
    assert client.delete(w.url("admin"), headers=w.h["admin"]).status_code == 204
    assert client.get(f"{API}/organizations/{w.org}", headers=w.h["admin"]).status_code == 404


def test_anyone_can_leave_but_only_themselves(client: TestClient) -> None:
    w = World(client)
    assert client.delete(w.url("viewer"), headers=w.h["viewer"]).status_code == 204
    me = client.get(f"{API}/me", headers=w.h["viewer"]).json()
    assert me["organizations"] == []
    assert client.delete(w.url("member"), headers=w.h["owner"]).status_code == 204


def test_unknown_member_or_role_is_404(client: TestClient) -> None:
    w = World(client)
    base = f"{API}/organizations/{w.org}/members"
    assert (
        client.patch(
            f"{base}/{uuid.uuid4()}",
            json={"role_id": w.roles["viewer"]["id"]},
            headers=w.h["owner"],
        ).status_code
        == 404
    )
    assert (
        client.patch(
            w.url("member"), json={"role_id": str(uuid.uuid4())}, headers=w.h["owner"]
        ).status_code
        == 404
    )
    assert client.delete(f"{base}/{uuid.uuid4()}", headers=w.h["owner"]).status_code == 404
