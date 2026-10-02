"""Concurrency: requests that could race must queue up on database locks, never both win.

Technique: the test holds a lock from a separate admin connection, starts the request in a thread,
and checks the request is really WAITING for that lock; releasing it lets the request finish.
"""

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import TEST_DATABASE_URL
from tests.tenancy_helpers import API, add_member, create_org, login, members_by_email, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")
ADMIN_URL = TEST_DATABASE_URL.replace("+psycopg", "")


@contextmanager
def holding(sql: str, *args: Any) -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    """Run SQL in a transaction left open (holding its locks) until the with-block ends.
    The block may call connection.commit(); otherwise everything is rolled back at the end."""
    with psycopg.connect(ADMIN_URL) as connection:
        connection.execute(sql, args)
        try:
            yield connection
        finally:
            connection.rollback()


def assert_blocked(*futures: Any) -> None:
    for future in futures:
        with pytest.raises(TimeoutError):
            future.result(timeout=0.8)


def test_two_owners_cannot_remove_each_other_at_the_same_time(client: TestClient) -> None:
    a, b = login(client, "alice"), login(client, "bob")
    org = create_org(client, a)["id"]
    add_member(org, "bob", "owner")
    members = members_by_email(client, a, org)
    url = f"{API}/organizations/{org}/members"
    with ThreadPoolExecutor(2) as pool:
        with holding("SELECT id FROM organizations WHERE id = %s FOR UPDATE", org):
            alice_removes_bob = pool.submit(
                TestClient(client.app).delete,
                f"{url}/{members['bob@example.com']['id']}",
                headers=a,
            )
            bob_removes_alice = pool.submit(
                TestClient(client.app).delete,
                f"{url}/{members['alice@example.com']['id']}",
                headers=b,
            )
            assert_blocked(alice_removes_bob, bob_removes_alice)
        results = sorted(
            [alice_removes_bob.result(10).status_code, bob_removes_alice.result(10).status_code]
        )
    assert results == [204, 409]  # exactly one succeeds; the other sees "last owner"
    with psycopg.connect(ADMIN_URL) as connection:
        owners = connection.execute(
            "SELECT count(*) FROM memberships m JOIN roles r ON r.id = m.role_id "
            "WHERE r.key = 'owner'"
        ).fetchone()
    assert owners == (1,)


def test_an_invitation_token_cannot_be_accepted_twice_at_once(client: TestClient) -> None:
    alice, bob = login(client, "alice"), login(client, "bob")
    org = create_org(client, alice)["id"]
    viewer = roles_by_key(client, alice, org)["viewer"]["id"]
    token = client.post(
        f"{API}/organizations/{org}/invitations",
        json={"email": "bob@example.com", "role_id": viewer},
        headers=alice,
    ).json()["token"]
    with ThreadPoolExecutor(2) as pool:
        with holding("SELECT id FROM invitations FOR UPDATE"):
            attempts = [
                pool.submit(
                    TestClient(client.app).post,
                    f"{API}/invitations/accept",
                    json={"token": token},
                    headers=bob,
                )
                for _ in range(2)
            ]
            assert_blocked(*attempts)
        codes = sorted(a.result(10).status_code for a in attempts)
    assert codes == [200, 404]
    with psycopg.connect(ADMIN_URL) as connection:
        assert connection.execute(
            "SELECT count(*) FROM memberships WHERE role_id = %s", (viewer,)
        ).fetchone() == (1,)


def test_simultaneous_invitations_for_one_email_produce_exactly_one(client: TestClient) -> None:
    alice = login(client, "alice")
    org = create_org(client, alice)["id"]
    viewer = roles_by_key(client, alice, org)["viewer"]["id"]
    body = {"email": "bob@example.com", "role_id": viewer}
    barrier = threading.Barrier(6)

    def invite() -> int:
        barrier.wait()
        response = TestClient(client.app).post(
            f"{API}/organizations/{org}/invitations", json=body, headers=alice
        )
        return int(response.status_code)

    with ThreadPoolExecutor(6) as pool:
        codes = sorted(f.result(20) for f in [pool.submit(invite) for _ in range(6)])
    assert codes == [201, 409, 409, 409, 409, 409]


def _custom_role(client: TestClient, owner: dict[str, str], org: str) -> str:
    response = client.post(
        f"{API}/organizations/{org}/roles", json={"name": "Temp", "permissions": []}, headers=owner
    )
    return str(response.json()["id"])


def test_a_role_that_someone_is_being_moved_into_is_not_deleted_out_from_under_them(
    client: TestClient,
) -> None:
    alice, carl = login(client, "alice"), login(client, "carl")
    org = create_org(client, alice)["id"]
    role = _custom_role(client, alice, org)
    add_member(org, "carl", "viewer")
    with ThreadPoolExecutor(1) as pool:
        # Someone is assigning carl to the role: the row is written but not committed yet.
        with holding(
            "UPDATE memberships SET role_id = %s "
            "WHERE user_id = (SELECT id FROM users WHERE auth_subject = 'carl')",
            role,
        ) as assigning:
            delete = pool.submit(
                TestClient(client.app).delete,
                f"{API}/organizations/{org}/roles/{role}",
                headers=alice,
            )
            assert_blocked(delete)
            assigning.commit()
        # After the assignment lands, the delete must see the role in use: a clean 409, not a crash.
        response = delete.result(10)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "role_in_use"
    assert carl  # (logged in so the membership could be created)


def test_assigning_a_role_waits_if_that_role_is_being_deleted(client: TestClient) -> None:
    alice, carl = login(client, "alice"), login(client, "carl")
    org = create_org(client, alice)["id"]
    add_member(org, "carl", "viewer")
    role = _custom_role(client, alice, org)
    member = members_by_email(client, alice, org)["carl@example.com"]["id"]
    with ThreadPoolExecutor(1) as pool:
        with holding(
            "SELECT id FROM roles WHERE id = %s FOR UPDATE", role
        ):  # a deletion in progress
            assign = pool.submit(
                TestClient(client.app).patch,
                f"{API}/organizations/{org}/members/{member}",
                json={"role_id": role},
                headers=alice,
            )
            assert_blocked(assign)
        assert assign.result(10).status_code == 200
    assert carl  # (logged in so the membership could be created)


def test_the_app_object_is_shared_between_clients(app: FastAPI) -> None:
    assert TestClient(app).app is app  # sanity check for the technique used above


def test_two_owners_cannot_demote_each_other_at_the_same_time(client: TestClient) -> None:
    a, b = login(client, "alice"), login(client, "bob")
    org = create_org(client, a)["id"]
    add_member(org, "bob", "owner")
    roles = roles_by_key(client, a, org)
    members = members_by_email(client, a, org)
    url = f"{API}/organizations/{org}/members"
    admin_role = {"role_id": roles["admin"]["id"]}
    with ThreadPoolExecutor(2) as pool:
        with holding("SELECT id FROM organizations WHERE id = %s FOR UPDATE", org):
            demote_bob = pool.submit(
                TestClient(client.app).patch,
                f"{url}/{members['bob@example.com']['id']}",
                json=admin_role,
                headers=a,
            )
            demote_alice = pool.submit(
                TestClient(client.app).patch,
                f"{url}/{members['alice@example.com']['id']}",
                json=admin_role,
                headers=b,
            )
            assert_blocked(demote_bob, demote_alice)
        codes = sorted([demote_bob.result(10).status_code, demote_alice.result(10).status_code])
    assert codes == [200, 409]
    with psycopg.connect(ADMIN_URL) as connection:
        owners = connection.execute(
            "SELECT count(*) FROM memberships m JOIN roles r ON r.id = m.role_id "
            "WHERE r.key = 'owner'"
        ).fetchone()
    assert owners == (1,)
