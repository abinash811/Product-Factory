"""Row-level security helpers: the database-side lock that backs up the tenant repository.

Postgres itself hides rows that do not belong to the current organization, so even a coding mistake
cannot leak another tenant's data. Policies read two values the API sets for each request
(see tenant_context.py): the current organization and the current user.

For a NEW tenant-owned table in a product migration:

    from app.core.db.rls import enable_tenant_isolation
    for statement in enable_tenant_isolation("invoices"):
        op.execute(statement)

The API must connect as a role that is not a superuser and has no BYPASSRLS (see
docs/NEW_PRODUCT_SETUP.md), otherwise these policies are ignored.
"""

CURRENT_ORG_FUNCTION = """
CREATE FUNCTION app_current_org() RETURNS uuid
LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.current_org', true), '')::uuid $$
"""

CURRENT_USER_FUNCTION = """
CREATE FUNCTION app_current_user() RETURNS uuid
LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid $$
"""


def enable_row_security(table: str) -> list[str]:
    """Turn security on for the table, including for the role that owns it."""
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
    ]


def enable_tenant_isolation(table: str) -> list[str]:
    """The standard policy: rows are visible and writable only inside the current organization."""
    return [
        *enable_row_security(table),
        f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
        "USING (organization_id = app_current_org()) "
        "WITH CHECK (organization_id = app_current_org())",
    ]


def disable_tenant_isolation(table: str) -> list[str]:
    return [
        f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
        f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
    ]
