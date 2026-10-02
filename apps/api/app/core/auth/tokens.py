"""Login-token verification. This is the ONLY module that knows how tokens are signed.

The API needs one thing from the login provider: a verified identity (who is this, and their email).
To change provider later, replace `build_verifier`; nothing else in the app touches tokens.

Security rules enforced here:
- Only asymmetric algorithms are accepted. "none" and shared-secret (HS*) tokens are rejected,
  which also blocks the classic "sign with the public key as a secret" attack.
- Signature, expiry, audience and issuer are all required to match.
- Signing keys come from our configured JWKS address, never from anything inside the token.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import AppError, UnauthenticatedError

ALLOWED_ALGORITHMS = ["ES256", "RS256", "EdDSA"]


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str  # the provider's stable user id
    email: str | None
    provider: str = "supabase"


class AuthUnavailableError(AppError):
    status_code, code = 503, "auth_unavailable"


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> VerifiedIdentity: ...


class JwtVerifier:
    """Verifies signed JWTs. `signing_key_for(token)` returns the key that should have signed it."""

    def __init__(
        self,
        signing_key_for: Callable[[str], Any],
        *,
        audience: str,
        issuer: str | None,
        leeway_seconds: int = 10,
        allow_anonymous: bool = False,
    ) -> None:
        self._signing_key_for = signing_key_for
        self._audience = audience
        self._issuer = issuer
        self._leeway = leeway_seconds
        self._allow_anonymous = allow_anonymous

    async def verify(self, token: str) -> VerifiedIdentity:
        try:
            key = await run_in_threadpool(self._signing_key_for, token)
            claims = jwt.decode(
                token,
                key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "sub", "aud"]},
            )
        except PyJWKClientConnectionError as exc:
            # Our problem (cannot reach the key server), not the user's: do not log them out.
            raise AuthUnavailableError("Login service is temporarily unavailable.") from exc
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError("Invalid or expired login token.") from exc

        if claims.get("is_anonymous") is True and not self._allow_anonymous:
            raise UnauthenticatedError("Anonymous sessions are not accepted.")
        email = claims.get("email")
        if _marked_unverified(claims):
            email = None  # never match invitations against an unconfirmed address
        return VerifiedIdentity(
            subject=str(claims["sub"]),
            email=email.strip().lower() if isinstance(email, str) and email.strip() else None,
        )


def _marked_unverified(claims: dict[str, Any]) -> bool:
    """True only when the provider explicitly says the email is unconfirmed (field names to be
    confirmed against a real Supabase token; absent means we cannot tell, so we trust the project's
    'confirm email' setting, which docs/NEW_PRODUCT_SETUP.md requires)."""
    metadata = claims.get("user_metadata")
    nested = metadata.get("email_verified") if isinstance(metadata, dict) else None
    return claims.get("email_verified") is False or nested is False


def build_verifier(settings: Settings) -> TokenVerifier | None:
    """None when login is not configured (the Factory itself holds no credentials)."""
    if not settings.auth_jwks_url:
        return None
    client = PyJWKClient(
        settings.auth_jwks_url,
        cache_jwk_set=True,
        lifespan=settings.auth_jwks_cache_seconds,
        timeout=5,
    )
    return JwtVerifier(
        lambda token: client.get_signing_key_from_jwt(token).key,
        audience=settings.auth_audience,
        issuer=settings.auth_issuer_url,
        leeway_seconds=settings.auth_clock_skew_seconds,
        allow_anonymous=settings.auth_allow_anonymous,
    )
