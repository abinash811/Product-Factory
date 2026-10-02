import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

# Must be set before `app` modules are imported (the limiter and module-level app read settings).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_DEFAULT", "1000/minute")
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://factory:factory@localhost:5432/factory_test"
)
# Tests must NEVER touch a real database, even if a developer has DATABASE_URL exported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.pop("MIGRATION_DATABASE_URL", None)

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.db import registry  # noqa: E402, F401
from app.core.db.base import Base  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.auth_helpers import SUPABASE_URL, build_test_verifier  # noqa: E402
from tests.db_models import ScratchBase  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[1]


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "database_url": TEST_DATABASE_URL,
        "supabase_url": SUPABASE_URL,
        **overrides,
    }
    return Settings(_env_file=None, **values)


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> None:
    """Bring the test database to the latest schema once per run (also proves migrations apply)."""
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def _truncate_all_tables() -> None:
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with psycopg.connect(TEST_DATABASE_URL.replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")


@pytest.fixture
def clean_db() -> Iterator[None]:
    """For tests that really commit data: start and finish with empty application tables."""
    _truncate_all_tables()
    yield
    _truncate_all_tables()


@pytest.fixture
def app() -> FastAPI:
    return create_app(make_settings(), token_verifier=build_test_verifier())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    limiter.reset()
    # raise_server_exceptions=False so we see the real 500 response a client would get.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back after each test, so tests never affect each other.

    Scratch tables (tests/db_models.py) are created inside the same transaction and vanish with it.
    """
    async with db_engine.connect() as connection:
        outer = await connection.begin()
        await connection.run_sync(ScratchBase.metadata.create_all)
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()
