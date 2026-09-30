"""Application settings, read from environment variables (never from code).

Variable names live in `.env.example`; real values live in host secret stores.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    project_name: str = "Product Factory API"
    version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Comma-separated list in the environment, e.g. "https://app.example.com,http://localhost:3000".
    frontend_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    rate_limit_default: str = "120/minute"
    redis_url: str | None = None  # shared rate-limit storage; in-memory when unset

    # None = on outside production, off in production.
    docs_enabled: bool | None = None

    # Database. Accepts postgresql://... (as Supabase shows it); converted to the psycopg 3 driver.
    # SecretStr keeps the password out of logs and reprs.
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://factory:factory@localhost:5432/factory"
    )
    # Migrations should use the DIRECT connection (not the pooler). Defaults to database_url.
    migration_database_url: SecretStr | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10
    # Set true when DATABASE_URL points at a transaction pooler (Supabase port 6543 / pgbouncer).
    db_pooler: bool = False

    @field_validator("database_url", "migration_database_url", mode="after")
    @classmethod
    def _use_psycopg_driver(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        url = value.get_secret_value()
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return SecretStr("postgresql+psycopg://" + url[len(prefix) :])
        return value

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        if self.app_env == "production":
            if "database_url" not in self.model_fields_set:
                raise ValueError("DATABASE_URL must be set explicitly in production")
            if not self.frontend_origins:
                raise ValueError("FRONTEND_ORIGINS must be set in production")
            bad = [o for o in self.frontend_origins if o == "*" or not o.startswith("https://")]
            if bad:
                raise ValueError(f"Production origins must be explicit https URLs, got: {bad}")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_on(self) -> bool:
        return self.docs_enabled if self.docs_enabled is not None else not self.is_production

    @property
    def alembic_database_url(self) -> str:
        return (self.migration_database_url or self.database_url).get_secret_value()

    @property
    def json_logs(self) -> bool:
        return self.app_env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
