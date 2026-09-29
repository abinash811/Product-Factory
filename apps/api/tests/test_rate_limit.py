import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter

router = APIRouter(prefix="/_r")


@router.get("/limited")
@limiter.limit("2/minute")
async def _limited(request: Request) -> dict[str, str]:
    return {"ok": "yes"}


@pytest.fixture(autouse=True)
def _routes(app: FastAPI) -> None:
    app.include_router(router)


def test_third_request_is_rate_limited_with_standard_error(client: TestClient) -> None:
    assert client.get("/_r/limited").status_code == 200
    assert client.get("/_r/limited").status_code == 200
    blocked = client.get("/_r/limited")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.json()["error"]["request_id"] == blocked.headers["X-Request-ID"]


def test_health_endpoints_are_never_limited(client: TestClient) -> None:
    assert all(client.get("/health/live").status_code == 200 for _ in range(30))
