"""THE isolation test. Every tenant-owned table must be covered here (see CLAUDE.md).

Two organizations, two owners. Each owner tries every route against the other's data.
"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.models import Organization, Role
from app.core.tenancy.roles import RoleRepository
from tests.conftest import TEST_DATABASE_URL
from tests.tenancy_helpers import API, create_org, login, members_by_email, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")


class TwoTenants:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.alice, self.bob = login(client, "alice"), login(client, "bob")
        self.a = create_org(client, self.alice, "Alpha")["id"]
        self.b = create_org(client, self.bob, "Beta")["id"]
        self.a_roles = roles_by_key(client, self.alice, self.a)
        self.b_roles = roles_by_key(client, self.bob, self.b)
        self.a_members = members_by_email(client, self.alice, self.a)
        self.b_members = members_by_email(client, self.bob, self.b)


def test_a_user_cannot_use_another_organizations_id_in_the_url(client: TestClient) -> None:
    t = TwoTenants(client)
    for path in ("", "/roles", "/members"):
        response = client.get(f"{API}/organizations/{t.b}{path}", headers=t.alice)
        assert response.status_code == 404, path
    assert (
        client.patch(
            f"{API}/organizations/{t.b}", json={"name": "Pwned"}, headers=t.alice
        ).status_code
        == 404
    )
    created = client.post(
        f"{API}/organizations/{t.b}/roles",
        json={"name": "Evil", "permissions": []},
        headers=t.alice,
    )
    assert created.status_code == 404
    assert client.get(f"{API}/organizations/{t.b}", headers=t.bob).json()["name"] == "Beta"


def test_ids_from_another_organization_never_work_inside_your_own(client: TestClient) -> None:
    t = TwoTenants(client)
    foreign_role = t.b_roles["viewer"]["id"]
    foreign_member = t.b_members["bob@example.com"]["id"]
    own_roles = f"{API}/organizations/{t.a}/roles"
    own_members = f"{API}/organizations/{t.a}/members"
    assert (
        client.patch(
            f"{own_roles}/{foreign_role}", json={"description": "x"}, headers=t.alice
        ).status_code
        == 404
    )
    assert client.delete(f"{own_roles}/{foreign_role}", headers=t.alice).status_code == 404
    assert client.delete(f"{own_members}/{foreign_member}", headers=t.alice).status_code == 404
    own_member = t.a_members["alice@example.com"]["id"]
    assigned = client.patch(
        f"{own_members}/{own_member}", json={"role_id": foreign_role}, headers=t.alice
    )
    assert assigned.status_code == 404  # cannot assign a role from another organization
    # Nothing in Beta changed.
    assert roles_by_key(client, t.bob, t.b)["viewer"] == t.b_roles["viewer"]
    assert members_by_email(client, t.bob, t.b) == t.b_members


def test_lists_only_ever_contain_your_own_rows(client: TestClient) -> None:
    t = TwoTenants(client)
    a_ids = {r["id"] for r in t.a_roles.values()}
    b_ids = {r["id"] for r in t.b_roles.values()}
    assert a_ids.isdisjoint(b_ids)
    me = client.get(f"{API}/me", headers=t.alice).json()
    assert [o["id"] for o in me["organizations"]] == [t.a]


async def test_the_repository_cannot_see_or_write_other_organizations(
    db_session: AsyncSession,
) -> None:
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    db_session.add_all(
        [Organization(id=org_a, name="A", slug="aaa"), Organization(id=org_b, name="B", slug="bbb")]
    )
    await db_session.flush()
    repo_a, repo_b = RoleRepository(db_session, org_a), RoleRepository(db_session, org_b)
    with pytest.raises(ValueError, match="different organization"):
        repo_a.add(Role(organization_id=org_b, name="Smuggled"))
    own = Role(name="Mine")
    repo_a.add(own)
    assert own.organization_id == org_a
    assert await repo_b.get(own.id) is None
    with pytest.raises(ValueError, match="different organization"):
        await repo_b.delete(own)


def test_the_database_itself_refuses_a_role_from_another_organization(client: TestClient) -> None:
    t = TwoTenants(client)
    plain_url = TEST_DATABASE_URL.replace("+psycopg", "")
    with (
        psycopg.connect(plain_url, autocommit=True) as connection,
        pytest.raises(psycopg.errors.ForeignKeyViolation),
    ):
        connection.execute(
            "UPDATE memberships SET role_id = %s WHERE id = %s",
            (t.b_roles["viewer"]["id"], t.a_members["alice@example.com"]["id"]),
        )
