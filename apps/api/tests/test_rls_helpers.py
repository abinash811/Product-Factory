"""The helper products use for their own tenant tables, tried on a scratch table."""

import psycopg
import pytest

from app.core.db.rls import (
    CURRENT_ORG_FUNCTION,
    disable_tenant_isolation,
    enable_tenant_isolation,
)
from tests.conftest import TEST_DATABASE_URL

ORG_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_statements_are_generated_for_the_standard_policy() -> None:
    statements = enable_tenant_isolation("invoices")
    assert statements[0] == "ALTER TABLE invoices ENABLE ROW LEVEL SECURITY"
    assert statements[1] == "ALTER TABLE invoices FORCE ROW LEVEL SECURITY"
    assert "organization_id = app_current_org()" in statements[2]
    assert "WITH CHECK" in statements[2]
    assert "DROP POLICY IF EXISTS tenant_isolation ON invoices" in disable_tenant_isolation(
        "invoices"
    )
    assert "app_current_org" in CURRENT_ORG_FUNCTION


def test_the_standard_policy_isolates_a_new_tenant_table() -> None:
    plain = TEST_DATABASE_URL.replace("+psycopg", "")
    with psycopg.connect(plain) as connection:  # admin; everything is rolled back at the end
        connection.execute(
            "CREATE TABLE scratch_invoices (id serial, organization_id uuid NOT NULL)"
        )
        connection.execute(
            "INSERT INTO scratch_invoices (organization_id) VALUES (%s), (%s)", (ORG_A, ORG_B)
        )
        for statement in enable_tenant_isolation("scratch_invoices"):
            connection.execute(statement)
        connection.execute("SET LOCAL ROLE factory_app")  # act as the API's limited role
        connection.execute("SELECT set_config('app.current_org', %s, true)", (ORG_A,))

        rows = connection.execute("SELECT organization_id::text FROM scratch_invoices").fetchall()
        assert rows == [(ORG_A,)]  # Beta's row is invisible
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO scratch_invoices (organization_id) VALUES (%s)", (ORG_B,)
            )
        connection.rollback()
