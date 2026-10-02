"""Creating organizations. The creator becomes Owner; starter roles come from the product config."""

import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.db.tenant_context import set_current_organization
from app.core.tenancy.models import Membership, Organization, Role
from app.core.tenancy.product_config import OWNER_KEY, ProductRoles


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:38].strip("-")
    return slug if len(slug) >= 3 else "org"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base
    while await session.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base[:32]}-{secrets.token_hex(3)}"
    return slug


async def create_organization(
    session: AsyncSession,
    user: User,
    product_roles: ProductRoles,
    name: str,
    slug: str | None,
) -> Organization:
    org_id = uuid.uuid4()
    await set_current_organization(session, org_id)  # row-level security needs it before inserts
    organization = Organization(
        id=org_id, name=name, slug=await _unique_slug(session, slug or slugify(name))
    )
    session.add(organization)
    await session.flush()

    roles = {
        default.key: Role(
            organization_id=org_id,
            key=default.key,
            name=default.name,
            description=default.description,
            permissions=list(default.permissions),
            is_system=True,
        )
        for default in product_roles.default_roles
    }
    session.add_all(roles.values())
    await session.flush()

    session.add(Membership(organization_id=org_id, user_id=user.id, role_id=roles[OWNER_KEY].id))
    await session.flush()
    return organization
