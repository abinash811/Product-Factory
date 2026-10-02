import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.auth.models import User
from app.core.db import get_session
from app.core.pagination import Page, PageParams, SortField, map_page, page_params, sorting
from app.core.rate_limit import limiter
from app.core.tenancy import invitations as service
from app.core.tenancy.context import OrgContext, require_permission
from app.core.tenancy.invitations import SORTABLE, InvitationRepository, Status, status_of
from app.core.tenancy.models import Invitation
from app.core.tenancy.roles import RoleRepository
from app.core.tenancy.schemas import (
    InvitationAccept,
    InvitationAccepted,
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    OrganizationOut,
    RoleRef,
)

org_router = APIRouter(prefix="/organizations/{org_id}/invitations", tags=["invitations"])
accept_router = APIRouter(prefix="/invitations", tags=["invitations"])

Session = Annotated[AsyncSession, Depends(get_session)]


def to_out(invitation: Invitation) -> InvitationOut:
    return InvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=RoleRef.model_validate(invitation.role),
        status=status_of(invitation),
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
    )


@org_router.get("")
async def list_invitations(
    ctx: Annotated[OrgContext, Depends(require_permission("invitations:read"))],
    session: Session,
    params: Annotated[PageParams, Depends(page_params)],
    sort: Annotated[list[SortField], Depends(sorting(SORTABLE, "-created_at"))],
    status: Status | None = None,
) -> Page[InvitationOut]:
    page = await InvitationRepository(session, ctx.organization.id).list(params, sort, status)
    return map_page(page, to_out)


@org_router.post("", status_code=201)
async def create_invitation(
    body: InvitationCreate,
    ctx: Annotated[OrgContext, Depends(require_permission("invitations:manage"))],
    session: Session,
) -> InvitationCreated:
    """Invite an email address. The one-time `token` is returned only here."""
    org_id = ctx.organization.id
    invitation, token = await service.create_invitation(
        ctx, InvitationRepository(session, org_id), RoleRepository(session, org_id), body
    )
    return InvitationCreated(**to_out(invitation).model_dump(), token=token)


@org_router.delete("/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_permission("invitations:manage"))],
    session: Session,
) -> None:
    await service.revoke_invitation(
        InvitationRepository(session, ctx.organization.id), invitation_id
    )


@accept_router.post("/accept")
@limiter.limit("20/hour")
async def accept_invitation(
    request: Request,
    body: InvitationAccept,
    user: Annotated[User, Depends(get_current_user)],
    session: Session,
) -> InvitationAccepted:
    """Join an organization with an invitation token. Needs a login whose email matches."""
    organization, role = await service.accept_invitation(session, user, body.token)
    return InvitationAccepted(
        organization=OrganizationOut.model_validate(organization), role=RoleRef.model_validate(role)
    )
