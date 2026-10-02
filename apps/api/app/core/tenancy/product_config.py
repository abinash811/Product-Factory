"""Loads and validates product/roles.config.json. A bad file stops the app at startup."""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.core.tenancy.permissions import CORE_PERMISSIONS, invalid_grants

OWNER_KEY = "owner"
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[5] / "product"


class PermissionDef(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")
    description: str = ""


class DefaultRole(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=60)
    description: str = ""
    permissions: list[str]


class ProductRoles(BaseModel):
    permissions: list[PermissionDef] = []
    default_roles: list[DefaultRole]

    @property
    def catalog(self) -> dict[str, str]:
        """Every valid permission with its description: factory core plus this product's own."""
        return {**CORE_PERMISSIONS, **{p.name: p.description for p in self.permissions}}

    @model_validator(mode="after")
    def _check(self) -> "ProductRoles":
        keys = [role.key for role in self.default_roles]
        if len(keys) != len(set(keys)):
            raise ValueError("default_roles keys must be unique")
        owner = next((r for r in self.default_roles if r.key == OWNER_KEY), None)
        if owner is None or owner.permissions != ["*"]:
            raise ValueError("an 'owner' default role holding exactly ['*'] is required")
        for role in self.default_roles:
            bad = invalid_grants(role.permissions, self.catalog)
            if bad:
                raise ValueError(f"role '{role.key}' has unknown permissions: {bad}")
        return self


def load_product_roles(config_dir: Path | None = None) -> ProductRoles:
    path = (config_dir or DEFAULT_CONFIG_DIR) / "roles.config.json"
    try:
        return ProductRoles.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"Invalid or missing product role config at {path}: {exc}") from exc
