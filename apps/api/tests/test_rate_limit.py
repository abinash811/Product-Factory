from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

from app.core.rate_limit import client_ip, limiter
from app.main import create_app
from tests.auth_helpers import build_test_verifier
from tests.conftest import make_settings

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


def _request(forwarded: str | None, hops: int, client_host: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    scope = {
        "type": "http",
        "headers": headers,
        "client": (client_host, 5000),
        "app": SimpleNamespace(state=SimpleNamespace(trusted_proxy_hops=hops)),
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("forwarded", "hops", "expected"),
    [
        ("6.6.6.6, 9.9.9.9", 0, "10.0.0.1"),  # no proxy configured: the header is ignored
        ("6.6.6.6, 9.9.9.9", 1, "9.9.9.9"),  # the entry our own proxy added (right-most)
        ("6.6.6.6, 9.9.9.9, 8.8.8.8", 2, "9.9.9.9"),  # two proxies: second from the right
        ("9.9.9.9", 2, "10.0.0.1"),  # fewer entries than proxies: do not guess
        (None, 1, "10.0.0.1"),  # header missing
        ("  ,, ", 1, "10.0.0.1"),  # junk
    ],
)
def test_client_ip_only_trusts_what_our_own_proxies_added(
    forwarded: str | None, hops: int, expected: str
) -> None:
    assert client_ip(_request(forwarded, hops)) == expected


def test_a_forged_forwarded_for_header_cannot_reset_the_limit() -> None:
    app = create_app(make_settings(trusted_proxy_hops=1), token_verifier=build_test_verifier())
    app.include_router(router)
    limiter.reset()
    with TestClient(app) as client:
        forged = [
            client.get(
                "/_r/limited", headers={"X-Forwarded-For": f"6.6.6.{i}, 9.9.9.9"}
            ).status_code
            for i in range(5)
        ]
        other_client = client.get("/_r/limited", headers={"X-Forwarded-For": "1.1.1.1, 8.8.8.8"})
    assert forged == [200, 200, 429, 429, 429]  # the left-hand entries changed, the limit did not
    assert other_client.status_code == 200  # a genuinely different client has its own allowance
