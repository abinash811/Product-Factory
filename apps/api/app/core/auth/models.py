"""Our own user record. The provider's id is stored beside it, never used as our primary key."""

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject"),)

    auth_provider: Mapped[str] = mapped_column()
    auth_subject: Mapped[str] = mapped_column()
    email: Mapped[str | None] = mapped_column(index=True)
