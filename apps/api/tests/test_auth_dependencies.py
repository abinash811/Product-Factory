from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.auth.dependencies import get_current_user, get_identity
from app.core.auth.models import User
from app.core.auth.tokens import VerifiedIdentity
from app.main import create_app
from tests.auth_helpers import auth_header, make_token
from tests.conftest import make_settings

pytestmark = pytest.mark.usefixtures("clean_db")
router = APIRouter(prefix="/_a")


@router.get("/identity")
async def _identity(identity: Annotated[VerifiedIdentity, Depends(get_identity)]) -> dict[str, str]:
    return {"subject": identity.subject}


@router.get("/me")
async def _me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str | None]:
    return {"id": str(user.id), "email": user.email}


@pytest.fixture(autouse=True)
def _routes(app: FastAPI) -> None:
    app.include_router(router)


def test_missing_token_is_401_with_challenge_header(client: TestClient) -> None:
    response = client.get("/_a/identity")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not-a-real-token"])
def test_malformed_or_invalid_authorization_is_401(client: TestClient, header: str) -> None:
    assert client.get("/_a/identity", headers={"Authorization": header}).status_code == 401


def test_valid_token_passes(client: TestClient) -> None:
    response = client.get("/_a/identity", headers=auth_header(make_token("sub-9")))
    assert response.json() == {"subject": "sub-9"}


def test_first_login_creates_our_own_user_and_later_logins_reuse_it(client: TestClient) -> None:
    first = client.get("/_a/me", headers=auth_header(make_token("sub-1", "a@example.com"))).json()
    second = client.get("/_a/me", headers=auth_header(make_token("sub-1", "a@example.com"))).json()
    other = client.get("/_a/me", headers=auth_header(make_token("sub-2", "b@example.com"))).json()
    assert first["id"] == second["id"]
    assert first["id"] != other["id"]


def test_email_changes_at_the_provider_are_picked_up(client: TestClient) -> None:
    client.get("/_a/me", headers=auth_header(make_token("sub-1", "old@example.com")))
    updated = client.get("/_a/me", headers=auth_header(make_token("sub-1", "new@example.com")))
    assert updated.json()["email"] == "new@example.com"


def test_login_not_configured_is_503_not_a_crash() -> None:
    app = create_app(make_settings(supabase_url=None))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/_a/identity", headers=auth_header(make_token()))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_unavailable"
