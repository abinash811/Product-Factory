"""Members of an organization: list, change role, remove. An organization always keeps an Owner."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.auth.models import User
from app.core.errors import ConflictError, PermissionDeniedError
from app.core.pagination import PageData, PageParams, SortField
from app.core.tenancy.context import OrgContext
from app.core.tenancy.models import Membership, Organization, Role
from app.core.tenancy.permissions import covers
from app.core.tenancy.product_config import OWNER_KEY
from app.core.tenancy.repository import TenantRepository
from app.core.tenancy.roles import RoleRepository

SORTABLE = ("created_at", "email")


class MembershipRepository(TenantRepository[Membership]):
    model = Membership
    not_found_message = "Member not found."

    async def list(self, params: PageParams, sort: Sequence[SortField]) -> PageData[Membership]:
        statement = self.select().join(User, User.id == Membership.user_id)
        columns = {"created_at": Membership.created_at, "email": User.email}
        for field in sort:
            column = columns[field.field]
            statement = statement.order_by(column.desc() if field.descending else column.asc())
        return await self.paginate(statement.order_by(Membership.id), params)

    async def lock_organization(self) -> None:
        """Serialise owner changes: concurrent requests queue here, so the last-owner rule holds."""
        await self.session.execute(
            select(Organization.id).where(Organization.id == self.organization_id).with_for_update()
        )

    async def owner_count(self) -> int:
        statement = (
            select(func.count())
            .select_from(Membership)
            .join(
                Role,
                (Role.id == Membership.role_id)
                & (Role.organization_id == Membership.organization_id),
            )
            .where(Membership.organization_id == self.organization_id, Role.key == OWNER_KEY)
        )
        return await self.session.scalar(statement) or 0


async def _protect_last_owner(repo: MembershipRepository, target: Membership) -> None:
    if target.role.key == OWNER_KEY and await repo.owner_count() <= 1:
        raise ConflictError("An organization must keep at least one Owner.", code="last_owner")


async def change_member_role(
    ctx: OrgContext,
    repo: MembershipRepository,
    roles: RoleRepository,
    membership_id: uuid.UUID,
    role_id: uuid.UUID,
) -> Membership:
    await repo.lock_organization()
    target = await repo.get_or_404(membership_id)
    new_role = await roles.get_shared_or_404(role_id)  # another organization's role is a 404
    # You can only move people between roles you could hold yourself.
    if not covers(ctx.permissions, new_role.permissions) or not covers(
        ctx.permissions, target.role.permissions
    ):
        raise PermissionDeniedError("You cannot assign or change a role more powerful than yours.")
    if new_role.key != OWNER_KEY:
        await _protect_last_owner(repo, target)
    target.role_id = new_role.id
    await repo.session.flush()
    await repo.session.refresh(target)
    return target


async def remove_member(
    ctx: OrgContext, repo: MembershipRepository, membership_id: uuid.UUID
) -> None:
    await repo.lock_organization()
    target = await repo.get_or_404(membership_id)
    if target.user_id != ctx.user.id:  # leaving yourself is always allowed; removing others is not
        if not ctx.can("members:manage"):
            raise PermissionDeniedError("You do not have permission to do this.")
        if not covers(ctx.permissions, target.role.permissions):
            raise PermissionDeniedError("You cannot remove someone more powerful than you.")
    await _protect_last_owner(repo, target)
    await repo.delete(target)
    await repo.session.flush()
