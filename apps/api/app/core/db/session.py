"""Engine and per-request session.

One session per request: it commits when the request succeeds and rolls back on any error,
so a half-finished request can never leave half-saved data.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict[str, Any] = {}
    if settings.db_pooler:
        connect_args["prepare_threshold"] = (
            None  # pgbouncer transaction mode has no prepared statements
        )
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # drop dead connections instead of failing a request
        connect_args=connect_args,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request session. Use it ONLY through `SessionDep` (below)."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


# IMPORTANT: scope="function" makes FastAPI finish the session (commit or roll back) BEFORE the
# response is sent. With the default scope the commit would run after the client already received
# "success", so a failed commit would be reported as success. Every use must go through this alias.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


async def check_database(engine: AsyncEngine) -> bool:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def check_rls_enforced(engine: AsyncEngine) -> bool:
    """False when the connected role could ignore row-level security (superuser or BYPASSRLS)."""
    async with engine.connect() as connection:
        bypasses = await connection.scalar(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
    return bypasses is False
