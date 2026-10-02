from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.auth.models import User
from app.core.db import get_session
from app.core.rate_limit import limiter
from app.core.tenancy.context import OrgContext, require_permission
from app.core.tenancy.organizations import create_organization
from app.core.tenancy.schemas import OrganizationCreate, OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", status_code=201)
@limiter.limit("10/hour")
async def create(
    request: Request,
    body: OrganizationCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationOut:
    """Create an organization. The caller becomes its Owner."""
    organization = await create_organization(
        session, user, request.app.state.product_roles, body.name, body.slug
    )
    return OrganizationOut.model_validate(organization)


@router.get("/{org_id}")
async def read(
    ctx: Annotated[OrgContext, Depends(require_permission("organization:read"))],
) -> OrganizationOut:
    return OrganizationOut.model_validate(ctx.organization)


@router.patch("/{org_id}")
async def update(
    body: OrganizationUpdate,
    ctx: Annotated[OrgContext, Depends(require_permission("organization:update"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationOut:
    ctx.organization.name = body.name
    await session.flush()
    return OrganizationOut.model_validate(ctx.organization)
