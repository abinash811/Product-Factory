"""The database-side lock. These tests bypass the API and the repository entirely: raw SQL, as the
limited role the API connects as. Even a coding mistake must not be able to cross organizations."""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db.base import Base
from app.core.db.session import check_rls_enforced
from app.main import create_app
from tests.conftest import TEST_APP_DATABASE_URL, TEST_DATABASE_URL, make_settings
from tests.tenancy_helpers import create_org, login, roles_by_key

pytestmark = pytest.mark.usefixtures("clean_db")
PLAIN = {
    "app": TEST_APP_DATABASE_URL.replace("+psycopg", ""),
    "admin": TEST_DATABASE_URL.replace("+psycopg", ""),
}


class Tenants:
    def __init__(self, client: TestClient) -> None:
        alice, bob = login(client, "alice"), login(client, "bob")
        self.a = create_org(client, alice, "Alpha")["id"]
        self.b = create_org(client, bob, "Beta")["id"]
        with psycopg.connect(PLAIN["admin"]) as admin:
            rows = admin.execute("SELECT auth_subject, id FROM users").fetchall()
        self.user = {sub: str(uid) for sub, uid in rows}
        self.b_roles = roles_by_key(client, bob, self.b)


@contextmanager
def app_session(
    org: str | None = None, user: str | None = None, invite_hash: str | None = None
) -> Iterator[psycopg.Cursor[tuple[object, ...]]]:
    """A transaction as the limited role, with the same per-request context the API sets."""
    with psycopg.connect(PLAIN["app"]) as connection, connection.cursor() as cursor:
        if org:
            cursor.execute("SELECT set_config('app.current_org', %s, true)", (org,))
        if user:
            cursor.execute("SELECT set_config('app.current_user_id', %s, true)", (user,))
        if invite_hash:
            cursor.execute("SELECT set_config('app.current_invite_hash', %s, true)", (invite_hash,))
        yield cursor
        connection.rollback()  # nothing these tests do may persist


def count(cursor: psycopg.Cursor[tuple[object, ...]], table: str, where: str = "true") -> int:
    row = cursor.execute(f"SELECT count(*) FROM {table} WHERE {where}").fetchone()  # noqa: S608
    assert row is not None
    value = row[0]
    assert isinstance(value, int)
    return value


def test_without_a_context_the_database_shows_nothing(client: TestClient) -> None:
    Tenants(client)
    with app_session() as cursor:
        assert [count(cursor, t) for t in ("roles", "memberships", "organizations")] == [0, 0, 0]


def test_inside_an_organization_only_its_own_rows_are_visible(client: TestClient) -> None:
    t = Tenants(client)
    with app_session(org=t.a) as cursor:
        assert count(cursor, "roles") == 4
        assert count(cursor, "roles", f"organization_id = '{t.b}'") == 0
        assert count(cursor, "memberships") == 1
        assert count(cursor, "organizations") == 1
        assert count(cursor, "organizations", f"id = '{t.b}'") == 0


def test_writes_cannot_touch_or_create_rows_in_another_organization(client: TestClient) -> None:
    t = Tenants(client)
    foreign_role = t.b_roles["viewer"]["id"]
    with app_session(org=t.a) as cursor:
        assert (
            cursor.execute("UPDATE roles SET name = 'x' WHERE id = %s", (foreign_role,)).rowcount
            == 0
        )
        assert cursor.execute("DELETE FROM roles WHERE id = %s", (foreign_role,)).rowcount == 0
        assert (
            cursor.execute("DELETE FROM memberships WHERE organization_id = %s", (t.b,)).rowcount
            == 0
        )
        assert (
            cursor.execute("UPDATE organizations SET name = 'x' WHERE id = %s", (t.b,)).rowcount
            == 0
        )
    with app_session(org=t.a) as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cursor.execute("INSERT INTO roles (organization_id, name) VALUES (%s, 'Smuggled')", (t.b,))
    with psycopg.connect(PLAIN["admin"]) as admin:  # nothing changed in Beta
        assert admin.execute(
            "SELECT count(*) FROM roles WHERE organization_id = %s", (t.b,)
        ).fetchone() == (4,)


def test_organizations_can_never_be_deleted_through_the_app_role(client: TestClient) -> None:
    t = Tenants(client)
    with app_session(org=t.a) as cursor:
        assert cursor.execute("DELETE FROM organizations WHERE id = %s", (t.a,)).rowcount == 0


def test_a_user_sees_only_their_own_memberships_before_choosing_an_organization(
    client: TestClient,
) -> None:
    t = Tenants(client)
    with app_session(user=t.user["alice"]) as cursor:
        assert count(cursor, "memberships") == 1
        assert count(cursor, "organizations") == 1
        assert count(cursor, "roles") == 1  # only the role their own membership points at
        assert count(cursor, "memberships", f"organization_id = '{t.b}'") == 0


def test_the_context_never_leaks_into_the_next_transaction(client: TestClient) -> None:
    t = Tenants(client)
    with psycopg.connect(PLAIN["app"], autocommit=False) as connection:
        connection.execute("SELECT set_config('app.current_org', %s, true)", (t.a,))
        assert connection.execute("SELECT count(*) FROM roles").fetchone() == (4,)
        connection.commit()
        assert connection.execute("SELECT count(*) FROM roles").fetchone() == (
            0,
        )  # same connection, new transaction


def test_every_table_with_an_organization_id_has_row_level_security_forced() -> None:
    """The guard for future tables: add a tenant table without policies and this test fails."""
    declared = {t.name for t in Base.metadata.sorted_tables if "organization_id" in t.c}
    with psycopg.connect(PLAIN["admin"]) as admin:
        rows = admin.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r'"
        ).fetchall()
    status = {name: (secured, forced) for name, secured, forced in rows}
    for table in declared | {"organizations"}:
        assert status[table] == (True, True), f"{table} has no forced row-level security"


async def test_the_app_role_cannot_bypass_security_but_the_admin_role_can() -> None:
    app_engine = create_async_engine(TEST_APP_DATABASE_URL, poolclass=NullPool)
    admin_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        assert await check_rls_enforced(app_engine) is True
        assert await check_rls_enforced(admin_engine) is False
    finally:
        await app_engine.dispose()
        await admin_engine.dispose()


def _production(url: str) -> TestClient:
    settings = make_settings(
        app_env="production", frontend_origins="https://a.example", database_url=url
    )
    return TestClient(create_app(settings))


def test_production_readiness_fails_if_the_database_role_could_bypass_security() -> None:
    with _production(TEST_DATABASE_URL) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["row_level_security"] == "fail"


def test_readiness_checks_security_whenever_login_is_configured_even_without_app_env() -> None:
    """A deploy that forgot APP_ENV=production must still not go live with a powerful role."""
    with TestClient(create_app(make_settings(database_url=TEST_DATABASE_URL))) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["row_level_security"] == "fail"


def test_the_app_role_cannot_tamper_with_migration_history() -> None:
    with (
        psycopg.connect(PLAIN["app"]) as connection,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        connection.execute("UPDATE alembic_version SET version_num = 'tampered'")


def test_production_readiness_passes_with_the_limited_role() -> None:
    with _production(TEST_APP_DATABASE_URL) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["row_level_security"] == "ok"


def test_development_logs_a_warning_when_the_role_bypasses_security(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with TestClient(create_app(make_settings(database_url=TEST_DATABASE_URL))):
        pass
    events = [
        json.loads(line).get("event")
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    assert "database_role_bypasses_row_level_security" in events


def test_cannot_create_organizations_or_memberships_outside_the_current_context(
    client: TestClient,
) -> None:
    t = Tenants(client)
    other_org = "11111111-1111-1111-1111-111111111111"
    with app_session(org=t.a) as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cursor.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (%s, 'X', 'xxx')", (other_org,)
        )
    with app_session() as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cursor.execute("INSERT INTO organizations (name, slug) VALUES ('X', 'xxx')")
    with app_session(org=t.a) as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cursor.execute(
            "INSERT INTO memberships (organization_id, user_id, role_id) "
            "SELECT %s, id, %s FROM users LIMIT 1",
            (t.b, t.b_roles["viewer"]["id"]),
        )


def _invite(client: TestClient, org: str, owner: dict[str, str], role_id: str, email: str) -> str:
    response = client.post(
        f"/api/v1/organizations/{org}/invitations",
        json={"email": email, "role_id": role_id},
        headers=owner,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def test_invitations_are_visible_only_in_their_organization_or_with_their_secret(
    client: TestClient,
) -> None:
    t = Tenants(client)
    alice, bob = login(client, "alice"), login(client, "bob")
    a_roles = roles_by_key(client, alice, t.a)
    token_a = _invite(client, t.a, alice, a_roles["viewer"]["id"], "x@example.com")
    _invite(client, t.b, bob, t.b_roles["viewer"]["id"], "y@example.com")
    hash_a = hashlib.sha256(token_a.encode()).hexdigest()

    with app_session() as cursor:
        assert count(cursor, "invitations") == 0
    with app_session(org=t.a) as cursor:
        assert count(cursor, "invitations") == 1
        assert count(cursor, "invitations", f"organization_id = '{t.b}'") == 0
    with app_session(invite_hash=hash_a) as cursor:  # holding the secret, no organization chosen
        assert count(cursor, "invitations") == 1
        assert cursor.execute("UPDATE invitations SET accepted_at = now()").rowcount == 1
        assert (
            cursor.execute("DELETE FROM invitations").rowcount == 0
        )  # a token holder cannot delete
    with app_session(invite_hash="0" * 64) as cursor:  # a wrong secret shows nothing
        assert count(cursor, "invitations") == 0


def test_invitations_cannot_be_written_into_another_organization(client: TestClient) -> None:
    t = Tenants(client)
    with app_session(org=t.a) as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cursor.execute(
            "INSERT INTO invitations (organization_id, email, role_id, token_hash, expires_at) "
            "VALUES (%s, 'z@example.com', %s, 'abc', now() + interval '1 day')",
            (t.b, t.b_roles["viewer"]["id"]),
        )
