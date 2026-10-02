import jwt
import pytest
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from pydantic import ValidationError

from app.core.auth.tokens import AuthUnavailableError, JwtVerifier, build_verifier
from app.core.errors import UnauthenticatedError
from tests.auth_helpers import (
    AUDIENCE,
    ISSUER,
    OTHER_KEY,
    SIGNING_KEY,
    build_test_verifier,
    hs256_signed_with_public_key,
    make_token,
)
from tests.conftest import make_settings


async def test_valid_token_gives_identity_with_normalised_email() -> None:
    identity = await build_test_verifier().verify(make_token("abc-123", " Person@Example.COM "))
    assert identity.subject == "abc-123"
    assert identity.email == "person@example.com"
    assert identity.provider == "supabase"


async def test_token_without_email_is_still_valid() -> None:
    assert (await build_test_verifier().verify(make_token(email=None))).email is None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(make_token(expires_in=-3600), id="expired"),
        pytest.param(make_token(aud="some-other-app"), id="wrong audience"),
        pytest.param(make_token(iss="https://evil.example/auth/v1"), id="wrong issuer"),
        pytest.param(make_token(key=OTHER_KEY), id="signed by someone else's key"),
        pytest.param(make_token(omit=["sub"]), id="no subject"),
        pytest.param(make_token(omit=["exp"]), id="no expiry"),
        pytest.param(make_token(omit=["aud"]), id="no audience"),
        pytest.param(hs256_signed_with_public_key(), id="HS256 signed with the public key"),
        pytest.param("not-a-token", id="garbage"),
        pytest.param("", id="empty"),
    ],
)
async def test_bad_tokens_are_rejected(token: str) -> None:
    with pytest.raises(UnauthenticatedError):
        await build_test_verifier().verify(token)


async def test_unsigned_token_is_rejected() -> None:
    claims = {"sub": "x", "aud": AUDIENCE, "iss": ISSUER, "exp": 9999999999}
    unsigned = jwt.encode(claims, "", algorithm="none")
    with pytest.raises(UnauthenticatedError):
        await build_test_verifier().verify(unsigned)


async def test_unknown_signing_key_is_a_login_failure() -> None:
    def no_such_key(_token: str) -> object:
        raise PyJWKClientError("Unable to find a signing key that matches")

    verifier = JwtVerifier(no_such_key, audience=AUDIENCE, issuer=ISSUER)
    with pytest.raises(UnauthenticatedError):
        await verifier.verify(make_token())


async def test_key_server_outage_is_503_not_a_logout() -> None:
    def outage(_token: str) -> object:
        raise PyJWKClientConnectionError("cannot reach key server")

    verifier = JwtVerifier(outage, audience=AUDIENCE, issuer=ISSUER)
    with pytest.raises(AuthUnavailableError) as caught:
        await verifier.verify(make_token())
    assert caught.value.status_code == 503


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"email_verified": False}, None),
        ({"user_metadata": {"email_verified": False}}, None),
        ({"email_verified": True}, "person@example.com"),
        ({"user_metadata": {"email_verified": True}}, "person@example.com"),
        ({}, "person@example.com"),  # no information: trust the project's confirm-email setting
    ],
)
async def test_an_email_the_provider_marks_unverified_is_not_trusted(
    claims: dict[str, object], expected: str | None
) -> None:
    identity = await build_test_verifier().verify(make_token(extra=claims))
    assert identity.email == expected


async def test_anonymous_sessions_are_rejected_unless_allowed() -> None:
    token = make_token(email=None, extra={"is_anonymous": True})
    with pytest.raises(UnauthenticatedError, match="Anonymous"):
        await build_test_verifier().verify(token)
    allowed = JwtVerifier(
        lambda _t: SIGNING_KEY.public_key(), audience=AUDIENCE, issuer=ISSUER, allow_anonymous=True
    )
    assert (await allowed.verify(token)).email is None


def test_verifier_is_only_built_when_login_is_configured() -> None:
    assert build_verifier(make_settings(supabase_url=None)) is None
    assert isinstance(build_verifier(make_settings()), JwtVerifier)


def test_settings_derive_key_address_and_issuer() -> None:
    s = make_settings(supabase_url="https://abc.supabase.co/")
    assert s.auth_jwks_url == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"
    assert s.auth_issuer_url == "https://abc.supabase.co/auth/v1"
    custom = make_settings(supabase_url="https://abc.supabase.co", auth_issuer="https://x/y")
    assert custom.auth_issuer_url == "https://x/y"
    assert make_settings(supabase_url=None).auth_jwks_url is None


def test_production_refuses_to_start_without_a_login_provider() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_URL"):
        make_settings(app_env="production", frontend_origins="https://a.example", supabase_url=None)
