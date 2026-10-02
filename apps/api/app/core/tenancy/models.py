"""Organizations (tenants), their roles and their members.

Every tenant-owned table in a product also uses `OrganizationOwnedMixin`; see `repository.py` for
how queries are kept inside one organization.
"""

import uuid

from sqlalchemy import (
    ARRAY,
    ForeignKey,
    ForeignKeyConstraint,
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
