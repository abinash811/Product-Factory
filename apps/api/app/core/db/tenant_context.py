"""Tells Postgres who is calling and which organization the request is for.

The values live only for the current transaction (set_config(..., true)), so they can never leak
into another request that reuses the connection. Row-level security policies read them.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_current_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_user_id', :value, true)"), {"value": str(user_id)}
    )


async def set_current_organization(session: AsyncSession, organization_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_org', :value, true)"), {"value": str(organization_id)}
    )


async def set_current_invite_hash(session: AsyncSession, token_hash: str) -> None:
    """Makes exactly one invitation (the one whose secret token the caller holds) usable."""
    await session.execute(
        text("SELECT set_config('app.current_invite_hash', :value, true)"), {"value": token_hash}
    )
