import json

import pytest
import structlog
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.logging import REDACTED, configure_logging, redact_sensitive
from app.main import create_app
from tests.conftest import make_settings


def test_origins_parse_from_comma_separated_string() -> None:
    s = make_settings(frontend_origins="http://a.test/, http://b.test")
    assert s.frontend_origins == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize("origins", ["*", "http://insecure.example", ""])
def test_production_rejects_unsafe_origins(origins: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(app_env="production", frontend_origins=origins)


def test_docs_default_follows_environment() -> None:
    assert make_settings().docs_on is True
    prod = make_settings(app_env="production", frontend_origins="https://a.example")
    assert prod.docs_on is False
    assert make_settings(docs_enabled=False).docs_on is False


def test_redaction_masks_sensitive_keys_only() -> None:
    out = redact_sensitive(
        None, "info", {"event": "x", "password": "p", "Authorization": "Bearer t", "user": "u"}
    )
    assert out["password"] == REDACTED
    assert out["Authorization"] == REDACTED
    assert out["user"] == "u"


def test_request_log_line_is_json_with_request_id(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app(make_settings())  # test env => JSON logs
    with TestClient(app) as client:
        client.get("/api/v1/nothing", headers={"X-Request-ID": "trace-abc-12345"})
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    entry = next(line for line in lines if line.get("event") == "request")
    assert entry["request_id"] == "trace-abc-12345"
    assert entry["status"] == 404
    assert entry["path"] == "/api/v1/nothing"
    assert "duration_ms" in entry


def test_console_logging_mode_configures_without_error() -> None:
    configure_logging("DEBUG", json_logs=False)
    structlog.get_logger("t").debug("hello")
    configure_logging("INFO", json_logs=True)
