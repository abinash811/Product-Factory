"""FastAPI dependencies: who is calling?

identity: Annotated[VerifiedIdentity, Depends(get_identity)]   # token checked, no database
user: Annotated[User, Depends(get_current_user)]               # plus our own user row
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.auth.tokens import AuthUnavailableError, TokenVerifier, VerifiedIdentity
from app.core.db import get_session
from app.core.errors import UnauthenticatedError

bearer_scheme = HTTPBearer(auto_error=False)  # auto_error off: we answer with our standard error


async def get_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> VerifiedIdentity:
    verifier: TokenVerifier | None = request.app.state.token_verifier
    if verifier is None:
        raise AuthUnavailableError("Login is not configured for this deployment.")
    if credentials is None:
        raise UnauthenticatedError("Missing bearer token.")
    return await verifier.verify(credentials.credentials)


async def get_current_user(
    identity: Annotated[VerifiedIdentity, Depends(get_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Finds our user row for the verified identity, creating it on first login."""
    statement = (
        insert(User)
        .values(
            auth_provider=identity.provider,
            auth_subject=identity.subject,
            email=identity.email,
        )
        .on_conflict_do_update(
            index_elements=[User.auth_provider, User.auth_subject],
            set_={"email": identity.email, "updated_at": func.now()},
        )
        .returning(User)
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(statement)).one()
