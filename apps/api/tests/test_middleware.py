import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def test_request_id_generated_and_returned(client: TestClient) -> None:
    response = client.get("/health/live")
    assert len(response.headers["X-Request-ID"]) == 32


def test_valid_incoming_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "trace-abc-12345"})
    assert response.headers["X-Request-ID"] == "trace-abc-12345"


@pytest.mark.parametrize(
    "bad", ["short", "x" * 200, "has spaces in it!!", "<script>alert(1)</script>"]
)
def test_unsafe_incoming_request_id_is_replaced(client: TestClient, bad: str) -> None:
    assert client.get("/health/live", headers={"X-Request-ID": bad}).headers["X-Request-ID"] != bad


def test_security_headers_present(client: TestClient) -> None:
    headers = client.get("/health/live").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in headers  # only in production


def test_docs_page_keeps_working_and_has_no_strict_csp(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


def test_production_enables_hsts_and_hides_docs() -> None:
    settings = make_settings(app_env="production", frontend_origins="https://app.example.com")
    with TestClient(create_app(settings)) as prod:
        assert "max-age" in prod.get("/health/live").headers["Strict-Transport-Security"]
        assert prod.get("/docs").status_code == 404
        assert prod.get("/api/v1/openapi.json").status_code == 404


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    ok = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert ok.headers["access-control-allow-credentials"] == "true"
    other = client.get("/health/live", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/v1/anything",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
