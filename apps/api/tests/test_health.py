from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.health import readiness_checks, register_readiness_check


@pytest.fixture(autouse=True)
def _clean_checks() -> Iterator[None]:
    readiness_checks.clear()
    yield
    readiness_checks.clear()


def test_live_is_ok(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_with_no_checks(client: TestClient) -> None:
    assert client.get("/health/ready").json() == {"status": "ok", "checks": {}}


def test_ready_reports_each_check(client: TestClient) -> None:
    async def good() -> bool:
        return True

    register_readiness_check("cache", good)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"cache": "ok"}


def test_ready_is_503_when_a_check_fails_or_raises(client: TestClient) -> None:
    async def bad() -> bool:
        return False

    async def boom() -> bool:
        raise RuntimeError("db down")

    register_readiness_check("database", bad)
    register_readiness_check("queue", boom)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": "fail", "queue": "fail"},
    }
    assert "db down" not in response.text  # internals are never exposed
