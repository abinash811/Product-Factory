"""FastAPI dependencies: who is calling?

identity: Annotated[VerifiedIdentity, Depends(get_identity)]   # token checked, no database
user: Annotated[User, Depends(get_current_user)]               # plus our own user row
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.auth.models import User
from app.core.auth.tokens import AuthUnavailableError, TokenVerifier, VerifiedIdentity
from app.core.db import SessionDep
from app.core.db.tenant_context import set_current_user
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
    session: SessionDep,
) -> User:
    """Finds our user row for the verified identity, creating it on first login."""
    existing = (
        await session.scalars(
            select(User).where(
                User.auth_provider == identity.provider, User.auth_subject == identity.subject
            )
        )
    ).first()
    if existing is not None:  # the common case: no write unless the email actually changed
        if identity.email is not None and existing.email != identity.email:
            existing.email = identity.email
            await session.flush()
        await set_current_user(session, existing.id)
        return existing
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
    user = (await session.scalars(statement)).one()
    await set_current_user(session, user.id)
    return user
