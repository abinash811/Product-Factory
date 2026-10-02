"""row level security for organizations, roles and memberships

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02 06:00:00+00:00

Policies, in plain words:
- A request only sees rows of the organization it is acting for (app.current_org).
- A user may also see their OWN memberships (and the organizations/roles those point at), which
  is what lets "GET /me" list a user's organizations before any organization is chosen.
- Writes are only allowed inside the current organization.
"""

from collections.abc import Sequence

from alembic import op

from app.core.db.rls import (
    CURRENT_ORG_FUNCTION,
    CURRENT_USER_FUNCTION,
    enable_row_security,
)

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MY_MEMBERSHIPS = "SELECT organization_id FROM memberships WHERE user_id = app_current_user()"
MY_ROLES = "SELECT role_id FROM memberships WHERE user_id = app_current_user()"


def upgrade() -> None:
    op.execute(CURRENT_ORG_FUNCTION)
    op.execute(CURRENT_USER_FUNCTION)

    # roles: the current organization's roles, plus the roles my own memberships point at.
    for statement in enable_row_security("roles"):
        op.execute(statement)
    op.execute(
        "CREATE POLICY roles_select ON roles FOR SELECT USING "
        f"(organization_id = app_current_org() OR id IN ({MY_ROLES}))"
    )
    for command, clause in (
        ("INSERT", "WITH CHECK (organization_id = app_current_org())"),
        (
            "UPDATE",
            "USING (organization_id = app_current_org()) WITH CHECK (organization_id = app_current_org())",
        ),
        ("DELETE", "USING (organization_id = app_current_org())"),
    ):
        op.execute(f"CREATE POLICY roles_{command.lower()} ON roles FOR {command} {clause}")

    # memberships: the current organization's members, plus my own memberships.
    for statement in enable_row_security("memberships"):
        op.execute(statement)
    op.execute(
        "CREATE POLICY memberships_select ON memberships FOR SELECT USING "
        "(organization_id = app_current_org() OR user_id = app_current_user())"
    )
    for command, clause in (
        ("INSERT", "WITH CHECK (organization_id = app_current_org())"),
        (
            "UPDATE",
            "USING (organization_id = app_current_org()) WITH CHECK (organization_id = app_current_org())",
        ),
        ("DELETE", "USING (organization_id = app_current_org())"),
    ):
        op.execute(
            f"CREATE POLICY memberships_{command.lower()} ON memberships FOR {command} {clause}"
        )

    # organizations: the current one, plus the ones I belong to. No policy for DELETE = never.
    for statement in enable_row_security("organizations"):
        op.execute(statement)
    op.execute(
        "CREATE POLICY organizations_select ON organizations FOR SELECT USING "
        f"(id = app_current_org() OR id IN ({MY_MEMBERSHIPS}))"
    )
    op.execute(
        "CREATE POLICY organizations_insert ON organizations FOR INSERT WITH CHECK (id = app_current_org())"
    )
    op.execute(
        "CREATE POLICY organizations_update ON organizations FOR UPDATE "
        "USING (id = app_current_org()) WITH CHECK (id = app_current_org())"
    )


def downgrade() -> None:
    for table, policies in (
        ("organizations", ("organizations_select", "organizations_insert", "organizations_update")),
        (
            "memberships",
            (
                "memberships_select",
                "memberships_insert",
                "memberships_update",
                "memberships_delete",
            ),
        ),
        ("roles", ("roles_select", "roles_insert", "roles_update", "roles_delete")),
    ):
        for policy in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION app_current_user()")
    op.execute("DROP FUNCTION app_current_org()")
