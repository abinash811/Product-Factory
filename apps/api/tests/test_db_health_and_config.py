from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.db import session as db_session_module
from app.main import create_app
from tests.conftest import make_settings


def test_ready_reports_database_ok(client: TestClient) -> None:
    body = client.get("/health/ready").json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_ready_is_503_when_the_database_is_unreachable() -> None:
    dead = make_settings(database_url="postgresql://factory:wrong@localhost:1/none")
    with TestClient(create_app(dead)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "fail"
    assert "wrong" not in response.text  # the password never leaks


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_plain_postgres_urls_are_converted_to_the_psycopg_driver(scheme: str) -> None:
    s = make_settings(database_url=f"{scheme}://u:p@db.example:5432/app")
    assert s.database_url.get_secret_value() == "postgresql+psycopg://u:p@db.example:5432/app"


def test_password_is_hidden_from_repr_and_logs() -> None:
    s = make_settings(database_url="postgresql://user:s3cret-pass@db.example/app")
    assert "s3cret-pass" not in repr(s)
    assert "s3cret-pass" not in str(s.model_dump())


def test_migrations_use_the_direct_url_when_given() -> None:
    plain = make_settings(database_url="postgresql://u:p@pooler:6543/app")
    assert plain.alembic_database_url.startswith("postgresql+psycopg://u:p@pooler")
    direct = make_settings(
        database_url="postgresql://u:p@pooler:6543/app",
        migration_database_url="postgresql://u:p@direct:5432/app",
    )
    assert "direct:5432" in direct.alembic_database_url


def test_production_requires_an_explicit_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, app_env="production", frontend_origins="https://a.example")


def test_pooler_mode_disables_prepared_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_create(url: str, **kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db_session_module, "create_async_engine", fake_create)
    db_session_module.build_engine(make_settings(db_pooler=True))
    assert captured["connect_args"] == {"prepare_threshold": None}
    db_session_module.build_engine(make_settings())
    assert captured["connect_args"] == {}
