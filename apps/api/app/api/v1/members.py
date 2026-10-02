import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, SortField, map_page, page_params, sorting
from app.core.tenancy import members as service
from app.core.tenancy.context import OrgContext, get_org_context, require_permission
from app.core.tenancy.members import SORTABLE, MembershipRepository
from app.core.tenancy.models import Membership
from app.core.tenancy.roles import RoleRepository
from app.core.tenancy.schemas import MemberOut, MemberUpdate, RoleRef

router = APIRouter(prefix="/organizations/{org_id}/members", tags=["members"])

Session = Annotated[AsyncSession, Depends(get_session)]


def to_out(membership: Membership) -> MemberOut:
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        role=RoleRef.model_validate(membership.role),
        created_at=membership.created_at,
    )


@router.get("")
async def list_members(
    ctx: Annotated[OrgContext, Depends(require_permission("members:read"))],
    session: Session,
    params: Annotated[PageParams, Depends(page_params)],
    sort: Annotated[list[SortField], Depends(sorting(SORTABLE, "created_at"))],
) -> Page[MemberOut]:
    page = await MembershipRepository(session, ctx.organization.id).list(params, sort)
    return map_page(page, to_out)


@router.patch("/{membership_id}")
async def change_role(
    membership_id: uuid.UUID,
    body: MemberUpdate,
    ctx: Annotated[OrgContext, Depends(require_permission("members:manage"))],
    session: Session,
) -> MemberOut:
    org_id = ctx.organization.id
    membership = await service.change_member_role(
        ctx,
        MembershipRepository(session, org_id),
        RoleRepository(session, org_id),
        membership_id,
        body.role_id,
    )
    return to_out(membership)


@router.delete("/{membership_id}", status_code=204)
async def remove_member(
    membership_id: uuid.UUID,
    ctx: Annotated[
        OrgContext, Depends(get_org_context)
    ],  # any member may leave; others need members:manage
    session: Session,
) -> None:
    await service.remove_member(
        ctx, MembershipRepository(session, ctx.organization.id), membership_id
    )
