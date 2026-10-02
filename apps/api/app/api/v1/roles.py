import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, SortField, map_page, page_params, sorting
from app.core.tenancy import roles as service
from app.core.tenancy.context import OrgContext, require_permission
from app.core.tenancy.roles import SORTABLE, RoleRepository
from app.core.tenancy.schemas import RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/organizations/{org_id}/roles", tags=["roles"])

Session = Annotated[AsyncSession, Depends(get_session)]


def _catalog(request: Request) -> dict[str, str]:
    catalog: dict[str, str] = request.app.state.product_roles.catalog
    return catalog


@router.get("")
async def list_roles(
    ctx: Annotated[OrgContext, Depends(require_permission("roles:read"))],
    session: Session,
    params: Annotated[PageParams, Depends(page_params)],
    sort: Annotated[list[SortField], Depends(sorting(SORTABLE, "name"))],
) -> Page[RoleOut]:
    page = await RoleRepository(session, ctx.organization.id).list(params, sort)
    return map_page(page, RoleOut.model_validate)


@router.post("", status_code=201)
async def create_role(
    request: Request,
    body: RoleCreate,
    ctx: Annotated[OrgContext, Depends(require_permission("roles:manage"))],
    session: Session,
) -> RoleOut:
    repo = RoleRepository(session, ctx.organization.id)
    return RoleOut.model_validate(await service.create_role(ctx, repo, _catalog(request), body))


@router.patch("/{role_id}")
async def update_role(
    request: Request,
    role_id: uuid.UUID,
    body: RoleUpdate,
    ctx: Annotated[OrgContext, Depends(require_permission("roles:manage"))],
    session: Session,
) -> RoleOut:
    repo = RoleRepository(session, ctx.organization.id)
    role = await service.update_role(ctx, repo, _catalog(request), role_id, body)
    return RoleOut.model_validate(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_permission("roles:manage"))],
    session: Session,
) -> None:
    await service.delete_role(ctx, RoleRepository(session, ctx.organization.id), role_id)
