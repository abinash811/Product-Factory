import hashlib
import uuid
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.auth_helpers import auth_header, make_token
from tests.conftest import TEST_DATABASE_URL
from tests.tenancy_helpers import API, add_member, create_org, login, members_by_email, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")
ADMIN_URL = TEST_DATABASE_URL.replace("+psycopg", "")


class Setup:
    """An organization with an owner (alice) and an admin (adam), plus a not-yet-member (bob)."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.alice, self.adam = login(client, "alice"), login(client, "adam")
        self.bob = login(client, "bob")
        self.org = create_org(client, self.alice)["id"]
        add_member(self.org, "adam", "admin")
        self.roles = roles_by_key(client, self.alice, self.org)
        self.url = f"{API}/organizations/{self.org}/invitations"

    def invite(
        self,
        who: dict[str, str] | None = None,
        email: str = "bob@example.com",
        role: str = "viewer",
        **extra: Any,
    ) -> Any:
        body = {"email": email, "role_id": self.roles[role]["id"], **extra}
        return self.client.post(self.url, json=body, headers=who or self.alice)

    def accept(self, token: str, who: dict[str, str] | None = None) -> Any:
        return self.client.post(
            f"{API}/invitations/accept", json={"token": token}, headers=who or self.bob
        )


def _sql(query: str, args: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    with psycopg.connect(ADMIN_URL, autocommit=True) as connection:
        cursor = connection.execute(query, args)
        return cursor.fetchall() if cursor.description else []


def test_invite_then_accept_makes_the_invitee_a_member_with_that_role(client: TestClient) -> None:
    s = Setup(client)
    created = s.invite()
    assert created.status_code == 201
    token = created.json()["token"]
    assert len(token) >= 40 and created.json()["status"] == "pending"

    accepted = s.accept(token)
    assert accepted.status_code == 200
    assert accepted.json()["role"]["key"] == "viewer"
    assert accepted.json()["organization"]["id"] == s.org

    me = client.get(f"{API}/me", headers=s.bob).json()
    assert [(o["id"], o["role"]["key"]) for o in me["organizations"]] == [(s.org, "viewer")]
    assert "bob@example.com" in members_by_email(client, s.alice, s.org)
    listed = client.get(s.url, headers=s.alice).json()["items"][0]
    assert listed["status"] == "accepted" and "token" not in listed
    assert client.get(f"{s.url}?status=accepted", headers=s.alice).json()["total"] == 1
    assert client.get(f"{s.url}?status=pending", headers=s.alice).json()["total"] == 0


def test_only_a_hash_of_the_token_is_stored(client: TestClient) -> None:
    s = Setup(client)
    token = s.invite().json()["token"]
    stored = _sql("SELECT token_hash FROM invitations")[0][0]
    assert stored == hashlib.sha256(token.encode()).hexdigest()
    assert token not in stored


def test_a_token_works_once(client: TestClient) -> None:
    s = Setup(client)
    token = s.invite().json()["token"]
    assert s.accept(token).status_code == 200
    again = s.accept(token)
    assert again.status_code == 404


def test_someone_else_cannot_use_a_token_and_the_invitation_stays_usable(
    client: TestClient,
) -> None:
    s = Setup(client)
    token = s.invite().json()["token"]
    mallory = login(client, "mallory")
    stolen = s.accept(token, mallory)
    assert stolen.status_code == 403
    assert stolen.json()["error"]["code"] == "invitation_email_mismatch"
    assert client.get(f"{API}/me", headers=mallory).json()["organizations"] == []
    assert s.accept(token).status_code == 200  # the real invitee can still accept


def test_a_login_without_an_email_cannot_accept(client: TestClient) -> None:
    s = Setup(client)
    token = s.invite().json()["token"]
    no_email = auth_header(make_token("ghost", email=None))
    assert s.accept(token, no_email).status_code == 403


def test_emails_are_matched_ignoring_case(client: TestClient) -> None:
    s = Setup(client)
    created = s.invite(email="Bob@Example.COM")
    assert created.json()["email"] == "bob@example.com"
    assert s.accept(created.json()["token"]).status_code == 200


@pytest.mark.parametrize("token", ["x" * 43, "short", "", "a" * 300])
def test_guessed_or_malformed_tokens_are_rejected(client: TestClient, token: str) -> None:
    s = Setup(client)
    response = s.accept(token)
    assert response.status_code in (404, 422)
    if response.status_code == 404:
        assert response.json()["error"]["message"] == "This invitation is invalid or has expired."


def test_expired_invitations_cannot_be_accepted_and_show_as_expired(client: TestClient) -> None:
    s = Setup(client)
    token = s.invite(expires_in_days=1).json()["token"]
    _sql("UPDATE invitations SET expires_at = now() - interval '1 minute'")
    assert s.accept(token).status_code == 404
    assert client.get(f"{s.url}?status=expired", headers=s.alice).json()["total"] == 1
    assert client.get(f"{s.url}?status=pending", headers=s.alice).json()["total"] == 0
    assert s.invite().status_code == 201  # an expired invitation does not block a fresh one


@pytest.mark.parametrize("days", [0, 31])
def test_invitation_lifetime_is_limited(client: TestClient, days: int) -> None:
    assert Setup(client).invite(expires_in_days=days).status_code == 422


def test_cannot_invite_current_members_or_the_same_email_twice(client: TestClient) -> None:
    s = Setup(client)
    member = s.invite(email="adam@example.com")
    assert member.status_code == 409 and member.json()["error"]["code"] == "already_member"
    first = s.invite()
    assert first.status_code == 201
    duplicate = s.invite()
    assert (
        duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "invitation_pending"
    )
    revoked = client.delete(f"{s.url}/{first.json()['id']}", headers=s.alice)
    assert revoked.status_code == 204
    assert s.invite().status_code == 201


def test_revoked_invitations_stop_working_and_accepted_ones_cannot_be_revoked(
    client: TestClient,
) -> None:
    s = Setup(client)
    created = s.invite().json()
    assert client.delete(f"{s.url}/{created['id']}", headers=s.alice).status_code == 204
    assert s.accept(created["token"]).status_code == 404
    again = s.invite().json()
    assert s.accept(again["token"]).status_code == 200
    blocked = client.delete(f"{s.url}/{again['id']}", headers=s.alice)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "invitation_accepted"
    assert client.delete(f"{s.url}/{uuid.uuid4()}", headers=s.alice).status_code == 404


def test_who_may_invite_whom(client: TestClient) -> None:
    s = Setup(client)
    assert s.invite(who=s.adam, role="member").status_code == 201  # admins can invite
    assert (
        s.invite(who=s.adam, email="x@example.com", role="owner").status_code == 403
    )  # not above themselves
    carl = login(client, "carl")
    add_member(s.org, "carl", "member")
    assert s.invite(who=carl, email="y@example.com").status_code == 403  # members cannot invite
    assert client.get(s.url, headers=carl).status_code == 403  # nor even list
    assert client.get(s.url, headers=s.adam).status_code == 200


def test_invitations_are_listed_paginated_and_sorted(client: TestClient) -> None:
    s = Setup(client)
    for name in ("a", "b", "c"):
        s.invite(email=f"{name}@example.com")
    page = client.get(f"{s.url}?sort=email&page_size=2", headers=s.alice).json()
    assert [i["email"] for i in page["items"]] == ["a@example.com", "b@example.com"]
    assert page["total"] == 3 and page["pages"] == 2
    assert client.get(f"{s.url}?status=nonsense", headers=s.alice).status_code == 422


def test_accepting_requires_login_and_a_user_who_is_already_a_member_gets_a_clear_error(
    client: TestClient,
) -> None:
    s = Setup(client)
    token = s.invite().json()["token"]
    assert client.post(f"{API}/invitations/accept", json={"token": token}).status_code == 401
    add_member(s.org, "bob", "viewer")  # bob joined another way in the meantime
    clash = s.accept(token)
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "already_member"
    assert (
        client.get(s.url, headers=s.alice).json()["items"][0]["status"] == "pending"
    )  # not consumed


def test_a_role_with_a_pending_invitation_cannot_be_deleted_until_it_is_revoked(
    client: TestClient,
) -> None:
    s = Setup(client)
    role = client.post(
        f"{API}/organizations/{s.org}/roles",
        json={"name": "Temp", "permissions": []},
        headers=s.alice,
    ).json()
    invitation = client.post(
        s.url, json={"email": "bob@example.com", "role_id": role["id"]}, headers=s.alice
    ).json()
    role_url = f"{API}/organizations/{s.org}/roles/{role['id']}"
    blocked = client.delete(role_url, headers=s.alice)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "role_in_use"
    client.delete(f"{s.url}/{invitation['id']}", headers=s.alice)
    assert client.delete(role_url, headers=s.alice).status_code == 204


def test_deleting_a_role_cleans_up_its_old_invitations(client: TestClient) -> None:
    s = Setup(client)
    role = client.post(
        f"{API}/organizations/{s.org}/roles",
        json={"name": "Temp", "permissions": []},
        headers=s.alice,
    ).json()
    token = client.post(
        s.url, json={"email": "bob@example.com", "role_id": role["id"]}, headers=s.alice
    ).json()["token"]
    assert s.accept(token).status_code == 200
    bob_member = members_by_email(client, s.alice, s.org)["bob@example.com"]["id"]
    viewer = s.roles["viewer"]["id"]
    client.patch(
        f"{API}/organizations/{s.org}/members/{bob_member}",
        json={"role_id": viewer},
        headers=s.alice,
    )
    role_url = f"{API}/organizations/{s.org}/roles/{role['id']}"
    assert (
        client.delete(role_url, headers=s.alice).status_code == 204
    )  # accepted invitation does not block
    assert client.get(s.url, headers=s.alice).json()["total"] == 0
