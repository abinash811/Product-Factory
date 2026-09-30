"""Migrations apply cleanly from an empty database, match the models, and roll back."""

from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_URL = "postgresql+psycopg://factory:factory@localhost:5432/factory_migrations_test"
PLAIN_URL = MIGRATIONS_URL.replace("+psycopg", "")


@pytest.fixture
def alembic_cfg() -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", MIGRATIONS_URL)
    cfg.attributes["configure_logger"] = False  # keep the app's own logging intact
    with psycopg.connect(PLAIN_URL, autocommit=True) as connection:
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    return cfg


def _current_revision() -> str | None:
    with psycopg.connect(PLAIN_URL) as connection:
        row = connection.execute("SELECT to_regclass('alembic_version')").fetchone()
        if row is None or row[0] is None:
            return None
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return version[0] if version else None


def test_upgrade_from_empty_reaches_head_and_downgrades_to_base(alembic_cfg: Config) -> None:
    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
    command.upgrade(alembic_cfg, "head")
    assert _current_revision() == head
    command.downgrade(alembic_cfg, "base")
    assert _current_revision() is None


def test_models_and_migrations_agree(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)  # raises if a model changed without a migration


def test_drift_between_database_and_models_is_detected(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    with psycopg.connect(PLAIN_URL, autocommit=True) as connection:
        connection.execute("CREATE TABLE rogue_table (id integer)")
    with pytest.raises(CommandError):
        command.check(alembic_cfg)
