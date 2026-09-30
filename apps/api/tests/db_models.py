"""Throwaway tables used only by tests. Separate base, so they never show up in migrations."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.db.base import NAMING_CONVENTION, TimestampMixin, UUIDPrimaryKeyMixin


class ScratchBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Widget(UUIDPrimaryKeyMixin, TimestampMixin, ScratchBase):
    __tablename__ = "test_widgets"
    name: Mapped[str] = mapped_column(unique=True)
