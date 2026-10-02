"""Which organization is this request for, and what may the caller do there?

    ctx: Annotated[OrgContext, Depends(require_permission("members:manage"))]

The organization comes from the URL (`/organizations/{org_id}/...`). Callers who are not members
get 404, exactly as if the organization did not exist, so existence is never revealed.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.auth.models import User
from app.core.db import get_session
from app.core.db.tenant_context import set_current_organization
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.tenancy.models import Membership, Organization, Role
from app.core.tenancy.permissions import has_permission

# Every permission named in a route is recorded here and checked against the product's catalog at
# startup, so a typo can never silently lock people out of a route.
registered_permissions: set[str] = set()


@dataclass(frozen=True)
class OrgContext:
    organization: Organization
    user: User
    membership: Membership

    @property
    def role(self) -> Role:
        return self.membership.role

    @property
    def permissions(self) -> tuple[str, ...]:
        return tuple(self.role.permissions)

    def can(self, permission: str) -> bool:
        return has_permission(self.role.permissions, permission)


async def get_org_context(
    org_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrgContext:
    await set_current_organization(session, org_id)
    membership = (
        await session.scalars(
            select(Membership).where(
                Membership.organization_id == org_id, Membership.user_id == user.id
            )
        )
    ).first()
    if membership is None:
        raise NotFoundError("Organization not found.")
    organization = await session.get_one(
        Organization, org_id
    )  # exists: the membership points at it
    return OrgContext(organization=organization, user=user, membership=membership)


def require_permission(*required: str) -> Callable[..., Awaitable[OrgContext]]:
    registered_permissions.update(required)

    async def dependency(ctx: Annotated[OrgContext, Depends(get_org_context)]) -> OrgContext:
        if not all(ctx.can(permission) for permission in required):
            raise PermissionDeniedError("You do not have permission to do this.")
        return ctx

    return dependency


def check_registered_permissions(catalog: dict[str, str]) -> None:
    unknown = sorted(p for p in registered_permissions if p not in catalog)
    if unknown:
        raise RuntimeError(f"Routes require permissions missing from the catalog: {unknown}")
