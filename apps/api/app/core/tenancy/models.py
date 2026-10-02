"""Organizations (tenants), their roles and their members.

Every tenant-owned table in a product also uses `OrganizationOwnedMixin`; see `repository.py` for
how queries are kept inside one organization.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.auth.models import User
from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationOwnedMixin:
    """Add to every table whose rows belong to one organization."""

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column()
    slug: Mapped[str] = mapped_column(unique=True)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, OrganizationOwnedMixin, Base):
    """A named bundle of permissions inside one organization (starter or custom)."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        UniqueConstraint("organization_id", "id"),  # target of the composite key on memberships
    )

    key: Mapped[str | None] = mapped_column()  # set for roles copied from the product's defaults
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(default="", server_default="")
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default=text("'{}'")
    )
    is_system: Mapped[bool] = mapped_column(default=False, server_default=false())


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, OrganizationOwnedMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        # The role must belong to the SAME organization: the database refuses anything else.
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            ondelete="RESTRICT",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(index=True)

    role: Mapped[Role] = relationship(lazy="joined", viewonly=True)
    user: Mapped[User] = relationship(lazy="joined", viewonly=True)


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, OrganizationOwnedMixin, Base):
    """An offer to join an organization in a role. Only a hash of the secret token is stored."""

    __tablename__ = "invitations"
    __table_args__ = (
        # At most one OPEN invitation per email and organization, even under concurrent requests.
        Index(
            "ux_invitations_open_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
        # The role must belong to the same organization. Deleting the role removes its old
        # invitations (the service refuses to delete a role that still has PENDING ones).
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            ondelete="CASCADE",
        ),
    )

    email: Mapped[str] = mapped_column(index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    role: Mapped[Role] = relationship(lazy="joined", viewonly=True)
