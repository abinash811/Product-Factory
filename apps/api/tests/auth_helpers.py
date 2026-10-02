"""Test-only helpers to mint login tokens with throwaway keys. Supabase is never contacted."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Iterable
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.auth.tokens import JwtVerifier

SUPABASE_URL = "https://test-project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
AUDIENCE = "authenticated"

SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def make_token(
    sub: str = "user-1",
    email: str | None = "person@example.com",
    *,
    key: Any = SIGNING_KEY,
    alg: str = "ES256",
    aud: str = AUDIENCE,
    iss: str = ISSUER,
    expires_in: int = 3600,
    omit: Iterable[str] = (),
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + expires_in,
    }
    payload.update(extra or {})
    for name in omit:
        payload.pop(name, None)
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": "test-key"})


def hs256_signed_with_public_key() -> str:
    """The 'algorithm confusion' attack: sign with HMAC using the public key as the secret."""
    public_pem = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(
        json.dumps({"sub": "attacker", "aud": AUDIENCE, "iss": ISSUER, "exp": now + 3600}).encode()
    )
    signature = hmac.new(public_pem, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{b64(signature)}"


def build_test_verifier() -> JwtVerifier:
    return JwtVerifier(
        lambda _token: SIGNING_KEY.public_key(), audience=AUDIENCE, issuer=ISSUER, leeway_seconds=0
    )


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
