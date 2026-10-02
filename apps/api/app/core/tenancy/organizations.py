"""Creating organizations. The creator becomes Owner; starter roles come from the product config."""

import re
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.db.tenant_context import set_current_organization
from app.core.errors import ConflictError
from app.core.tenancy.models import Membership, Organization, Role
from app.core.tenancy.product_config import OWNER_KEY, ProductRoles


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:38].strip("-")
    return slug if len(slug) >= 3 else "org"


async def _insert_with_unique_slug(
    session: AsyncSession, org_id: uuid.UUID, name: str, base: str, *, explicit: bool
) -> Organization:
    """Slugs are unique across ALL organizations, but row-level security hides other tenants from
    us, so we cannot check first. The database's unique constraint decides; we retry on a clash."""
    candidate = base
    for _ in range(5):
        organization = Organization(id=org_id, name=name, slug=candidate)
        try:
            async with session.begin_nested():
                session.add(organization)
                await session.flush()
            return organization
        except IntegrityError as exc:
            if "uq_organizations_slug" not in str(exc.orig):
                raise
            if explicit:
                raise ConflictError("This slug is already taken.", code="slug_taken") from exc
            candidate = f"{base[:32]}-{secrets.token_hex(3)}"
    raise ConflictError("Could not find a free slug, please choose one.", code="slug_taken")


async def create_organization(
    session: AsyncSession,
    user: User,
    product_roles: ProductRoles,
    name: str,
    slug: str | None,
) -> Organization:
    org_id = uuid.uuid4()
    await set_current_organization(session, org_id)  # row-level security needs it before inserts
    organization = await _insert_with_unique_slug(
        session, org_id, name, slug or slugify(name), explicit=slug is not None
    )

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
