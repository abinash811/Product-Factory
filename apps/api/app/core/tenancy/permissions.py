"""Permission rules. Pure functions, no database.

A permission is "resource:action" (for example "invoices:create"). Roles grant permissions, and a
grant may be a wildcard: "*" (everything) or "invoices:*" (every action on one resource).

Escalation rule used everywhere: you can only hand out what you hold yourself.
"""

import re
from collections.abc import Collection, Iterable

GRANT_PATTERN = re.compile(r"^(\*|[a-z][a-z0-9_]*:(\*|[a-z][a-z0-9_]*))$")

# Permissions the factory itself needs. Products add their own in product/roles.config.json.
CORE_PERMISSIONS: dict[str, str] = {
    "organization:read": "View the organization",
    "organization:update": "Rename the organization",
    "members:read": "View members",
    "members:manage": "Change members' roles and remove members",
    "roles:read": "View roles",
    "roles:manage": "Create, edit and delete roles",
    "invitations:read": "View invitations",
    "invitations:manage": "Invite people and revoke invitations",
}


def grant_matches(grant: str, required: str) -> bool:
    if grant in ("*", required):
        return True
    return grant.endswith(":*") and required.startswith(grant[:-1])


def has_permission(grants: Iterable[str], required: str) -> bool:
    return any(grant_matches(grant, required) for grant in grants)


def grant_is_covered(holder_grants: Collection[str], grant: str) -> bool:
    """Can someone holding `holder_grants` hand out `grant`?"""
    if "*" in holder_grants:
        return True
    if grant == "*":
        return False
    if grant.endswith(":*"):
        return grant in holder_grants  # a resource-wide grant needs the same resource-wide grant
    return has_permission(holder_grants, grant)


def covers(holder_grants: Collection[str], wanted: Iterable[str]) -> bool:
    return all(grant_is_covered(holder_grants, grant) for grant in wanted)


def invalid_grants(grants: Iterable[str], catalog: Collection[str]) -> list[str]:
    """Grants that are malformed or name a permission the product does not define."""
    resources = {name.split(":", 1)[0] for name in catalog}
    bad: list[str] = []
    for grant in grants:
        if not GRANT_PATTERN.fullmatch(grant):
            bad.append(grant)
        elif grant == "*" or grant in catalog:
            continue
        elif not (grant.endswith(":*") and grant.split(":", 1)[0] in resources):
            bad.append(grant)
    return bad
