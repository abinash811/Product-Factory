"""Custom roles. Rules: you cannot grant what you do not hold, and the Owner role is untouchable."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.errors import BadRequestError, ConflictError, PermissionDeniedError
from app.core.pagination import PageData, PageParams, SortField
from app.core.tenancy.context import OrgContext
from app.core.tenancy.models import Membership, Role
from app.core.tenancy.permissions import covers, invalid_grants
from app.core.tenancy.product_config import OWNER_KEY
from app.core.tenancy.repository import TenantRepository
from app.core.tenancy.schemas import RoleCreate, RoleUpdate

SORTABLE = ("name", "created_at")


class RoleRepository(TenantRepository[Role]):
    model = Role
    not_found_message = "Role not found."

    async def list(self, params: PageParams, sort: Sequence[SortField]) -> PageData[Role]:
        statement = self.select()
        for field in sort:
            column = getattr(Role, field.field)
            statement = statement.order_by(column.desc() if field.descending else column.asc())
        return await self.paginate(statement.order_by(Role.id), params)

    async def name_taken(self, name: str, *, excluding: uuid.UUID | None = None) -> bool:
        statement = self.select().where(func.lower(Role.name) == name.lower())
        if excluding:
            statement = statement.where(Role.id != excluding)
        return (await self.session.scalars(statement)).first() is not None

    async def member_count(self, role_id: uuid.UUID) -> int:
        statement = select(func.count()).where(
            Membership.organization_id == self.organization_id, Membership.role_id == role_id
        )
        return await self.session.scalar(statement) or 0


def _check_grants(ctx: OrgContext, grants: list[str], catalog: dict[str, str]) -> None:
    bad = invalid_grants(grants, catalog)
    if bad:
        raise BadRequestError(f"Unknown permissions: {', '.join(bad)}.", code="invalid_permissions")
    if not covers(ctx.permissions, grants):
        raise PermissionDeniedError("You cannot grant permissions you do not hold yourself.")


def _check_not_above_you(ctx: OrgContext, role: Role) -> None:
    if not covers(ctx.permissions, role.permissions):
        raise PermissionDeniedError("You cannot change a role that is more powerful than yours.")


async def create_role(
    ctx: OrgContext, repo: RoleRepository, catalog: dict[str, str], data: RoleCreate
) -> Role:
    _check_grants(ctx, data.permissions, catalog)
    if await repo.name_taken(data.name):
        raise ConflictError("A role with this name already exists.", code="role_name_taken")
    role = repo.add(
        Role(
            name=data.name,
            description=data.description,
            permissions=sorted(set(data.permissions)),
            is_system=False,
        )
    )
    await repo.session.flush()
    return role


async def update_role(
    ctx: OrgContext,
    repo: RoleRepository,
    catalog: dict[str, str],
    role_id: uuid.UUID,
    data: RoleUpdate,
) -> Role:
    role = await repo.get_or_404(role_id)
    if role.key == OWNER_KEY:
        raise ConflictError("The Owner role cannot be changed.", code="owner_role_locked")
    _check_not_above_you(ctx, role)
    if data.name is not None and data.name != role.name:
        if role.is_system:
            raise ConflictError("Starter roles cannot be renamed.", code="system_role_locked")
        if await repo.name_taken(data.name, excluding=role.id):
            raise ConflictError("A role with this name already exists.", code="role_name_taken")
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        _check_grants(ctx, data.permissions, catalog)
        role.permissions = sorted(set(data.permissions))
    await repo.session.flush()
    return role


async def delete_role(ctx: OrgContext, repo: RoleRepository, role_id: uuid.UUID) -> None:
    role = await repo.get_or_404(role_id)
    if role.is_system:
        raise ConflictError("Starter roles cannot be deleted.", code="system_role_locked")
    _check_not_above_you(ctx, role)
    if await repo.member_count(role.id):
        raise ConflictError("Move members to another role first.", code="role_in_use")
    await repo.delete(role)
    await repo.session.flush()
