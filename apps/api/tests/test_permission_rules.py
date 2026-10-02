import json
from pathlib import Path

import pytest

from app.core.tenancy.context import check_registered_permissions
from app.core.tenancy.permissions import covers, grant_matches, has_permission, invalid_grants
from app.core.tenancy.product_config import load_product_roles

CATALOG = {"invoices:create": "", "invoices:read": "", "members:manage": ""}


@pytest.mark.parametrize(
    ("grant", "required", "expected"),
    [
        ("*", "anything:at_all", True),
        ("invoices:create", "invoices:create", True),
        ("invoices:*", "invoices:create", True),
        ("invoices:*", "invoicesx:create", False),
        ("invoices:create", "invoices:read", False),
        ("invoices:read", "invoices:*", False),
    ],
)
def test_grant_matching(grant: str, required: str, expected: bool) -> None:
    assert grant_matches(grant, required) is expected


def test_has_permission_over_several_grants() -> None:
    assert has_permission(["a:read", "invoices:*"], "invoices:create")
    assert not has_permission([], "invoices:create")


@pytest.mark.parametrize(
    ("holder", "wanted", "expected"),
    [
        (["*"], ["*", "x:*", "x:y"], True),
        (["invoices:*"], ["invoices:create"], True),
        (["invoices:*"], ["invoices:*"], True),
        (["invoices:create"], ["invoices:*"], False),  # cannot hand out a wider grant than you hold
        (["invoices:create"], ["*"], False),
        (["invoices:create"], ["invoices:create", "invoices:read"], False),
        (["invoices:create"], [], True),
    ],
)
def test_you_can_only_grant_what_you_hold(
    holder: list[str], wanted: list[str], expected: bool
) -> None:
    assert covers(holder, wanted) is expected


def test_invalid_grants_are_reported() -> None:
    assert invalid_grants(["*", "invoices:create", "invoices:*"], CATALOG) == []
    assert invalid_grants(["invoices:delete", "nope:*", "Bad Name", "x"], CATALOG) == [
        "invoices:delete",
        "nope:*",
        "Bad Name",
        "x",
    ]


def _write(tmp_path: Path, data: dict[str, object]) -> Path:
    (tmp_path / "roles.config.json").write_text(json.dumps(data))
    return tmp_path


OWNER = {"key": "owner", "name": "Owner", "permissions": ["*"]}


def test_shipped_product_config_is_valid() -> None:
    config = load_product_roles()
    assert "owner" in {r.key for r in config.default_roles}
    assert "members:manage" in config.catalog


def test_product_can_add_its_own_permissions(tmp_path: Path) -> None:
    data = {
        "permissions": [{"name": "invoices:create", "description": "Create invoices"}],
        "default_roles": [
            OWNER,
            {"key": "cashier", "name": "Cashier", "permissions": ["invoices:*"]},
        ],
    }
    config = load_product_roles(_write(tmp_path, data))
    assert "invoices:create" in config.catalog


@pytest.mark.parametrize(
    "data",
    [
        {"default_roles": [{"key": "admin", "name": "Admin", "permissions": ["*"]}]},
        {"default_roles": [{**OWNER, "permissions": ["members:read"]}]},
        {"default_roles": [OWNER, {"key": "x", "name": "X", "permissions": ["typo:thing"]}]},
        {"default_roles": [OWNER, OWNER]},
    ],
    ids=["no owner", "owner not everything", "unknown permission", "duplicate key"],
)
def test_bad_product_config_stops_startup(tmp_path: Path, data: dict[str, object]) -> None:
    with pytest.raises(RuntimeError, match="product role config"):
        load_product_roles(_write(tmp_path, data))


def test_missing_or_broken_config_file_stops_startup(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        load_product_roles(tmp_path)
    (tmp_path / "roles.config.json").write_text("{not json")
    with pytest.raises(RuntimeError):
        load_product_roles(tmp_path)


def test_route_permissions_missing_from_catalog_are_caught_at_startup() -> None:
    with pytest.raises(RuntimeError, match="missing from the catalog"):
        check_registered_permissions({"only:this": ""})
