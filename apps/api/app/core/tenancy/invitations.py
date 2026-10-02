"""Invitations: invite an email address to a role; the invitee accepts with a secret token.

The token is random (256 bits) and only its SHA-256 hash is stored, so a database leak cannot be
used to join organizations. Accepting needs the token AND a login whose email matches.
"""

import hashlib
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.db.tenant_context import set_current_invite_hash, set_current_organization
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.pagination import PageData, PageParams, SortField
from app.core.tenancy.context import OrgContext
from app.core.tenancy.models import Invitation, Membership, Organization, Role
from app.core.tenancy.permissions import covers
from app.core.tenancy.repository import TenantRepository
from app.core.tenancy.roles import RoleRepository
from app.core.tenancy.schemas import InvitationCreate

SORTABLE = ("created_at", "expires_at", "email")
Status = Literal["pending", "accepted", "expired"]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def status_of(invitation: Invitation) -> Status:
    if invitation.accepted_at is not None:
        return "accepted"
    return "expired" if invitation.expires_at <= datetime.now(UTC) else "pending"


class InvitationRepository(TenantRepository[Invitation]):
    model = Invitation
    not_found_message = "Invitation not found."

    async def list(
        self, params: PageParams, sort: Sequence[SortField], status: Status | None
    ) -> PageData[Invitation]:
        statement = self.select()
        now = datetime.now(UTC)
        if status == "accepted":
            statement = statement.where(Invitation.accepted_at.is_not(None))
        elif status == "pending":
            statement = statement.where(
                Invitation.accepted_at.is_(None), Invitation.expires_at > now
            )
        elif status == "expired":
            statement = statement.where(
                Invitation.accepted_at.is_(None), Invitation.expires_at <= now
            )
        for field in sort:
            column = getattr(Invitation, field.field)
            statement = statement.order_by(column.desc() if field.descending else column.asc())
        return await self.paginate(statement.order_by(Invitation.id), params)

    async def pending_for_email(self, email: str) -> Invitation | None:
        statement = self.select().where(
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > datetime.now(UTC),
        )
        return (await self.session.scalars(statement)).unique().first()


async def create_invitation(
    ctx: OrgContext,
    repo: InvitationRepository,
    roles: RoleRepository,
    data: InvitationCreate,
) -> tuple[Invitation, str]:
    role = await roles.get_shared_or_404(data.role_id)
    if not covers(ctx.permissions, role.permissions):
        raise PermissionDeniedError(
            "You cannot invite someone into a role more powerful than yours."
        )
    email = data.email.strip().lower()
    already_member = await repo.session.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == repo.organization_id, User.email == email)
    )
    if already_member:
        raise ConflictError("This person is already a member.", code="already_member")
    # Expired, unaccepted invitations for this email are dead weight and would block a new one.
    await repo.session.execute(
        delete(Invitation).where(
            Invitation.organization_id == repo.organization_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at <= func.now(),
        )
    )
    if await repo.pending_for_email(email):
        raise ConflictError(
            "A pending invitation for this email exists. Revoke it first.",
            code="invitation_pending",
        )
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        email=email,
        role_id=role.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=data.expires_in_days),
        invited_by_user_id=ctx.user.id,
    )
    try:
        async with repo.session.begin_nested():
            repo.add(invitation)
            await repo.session.flush()
    except IntegrityError as exc:  # a concurrent request invited the same email first
        raise ConflictError(
            "A pending invitation for this email exists. Revoke it first.",
            code="invitation_pending",
        ) from exc
    await repo.session.refresh(invitation)
    return invitation, token


async def revoke_invitation(
    ctx: OrgContext, repo: InvitationRepository, invitation_id: uuid.UUID
) -> None:
    invitation = await repo.get_or_404(invitation_id)
    if not covers(ctx.permissions, invitation.role.permissions):
        raise PermissionDeniedError("You cannot revoke an invitation more powerful than your role.")
    if invitation.accepted_at is not None:
        raise ConflictError("This invitation was already accepted.", code="invitation_accepted")
    await repo.delete(invitation)
    await repo.session.flush()


async def accept_invitation(
    session: AsyncSession, user: User, verified_email: str | None, token: str
) -> tuple[Organization, Role]:
    """Join the organization the token belongs to. Atomic: two accepts cannot both win."""
    await set_current_invite_hash(session, hash_token(token))
    invitation = (
        (
            await session.scalars(
                select(Invitation)
                .where(Invitation.token_hash == hash_token(token))
                .with_for_update(of=Invitation)  # lock the invitation row only
            )
        )
        .unique()
        .first()
    )
    # One generic answer for unknown, used and expired tokens: nothing is revealed to guessers.
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= datetime.now(UTC)
    ):
        raise NotFoundError("This invitation is invalid or has expired.")
    # Compare with the email in THIS login's verified token, not the one stored from earlier logins.
    if not verified_email or verified_email != invitation.email:
        raise PermissionDeniedError(
            "This invitation was sent to a different email address.",
            code="invitation_email_mismatch",
        )

    await set_current_organization(session, invitation.organization_id)
    already = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == invitation.organization_id, Membership.user_id == user.id
        )
    )
    if already:
        raise ConflictError("You are already a member of this organization.", code="already_member")
    session.add(
        Membership(
            organization_id=invitation.organization_id, user_id=user.id, role_id=invitation.role_id
        )
    )
    invitation.accepted_at = datetime.now(UTC)
    invitation.accepted_by_user_id = user.id
    await session.flush()
    # Load these only now: until the organization context was set, row-level security hid them.
    organization = await session.get_one(Organization, invitation.organization_id)
    role = await session.get_one(Role, invitation.role_id)
    return organization, role
