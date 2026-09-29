import os
from collections.abc import Iterator
from typing import Any

# Must be set before `app` modules are imported (the limiter reads settings at import time).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_DEFAULT", "1000/minute")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import limiter
from app.main import create_app


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {"app_env": "test", **overrides}
    return Settings(_env_file=None, **values)


@pytest.fixture
def app() -> FastAPI:
    return create_app(make_settings())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    limiter.reset()
    # raise_server_exceptions=False so we see the real 500 response a client would get.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
