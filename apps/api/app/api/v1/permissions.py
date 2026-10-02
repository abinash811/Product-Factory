from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.auth.dependencies import get_current_user
from app.core.auth.models import User
from app.core.tenancy.schemas import PermissionOut

router = APIRouter(tags=["permissions"])


@router.get("/permissions")
async def list_permissions(
    request: Request, _user: Annotated[User, Depends(get_current_user)]
) -> list[PermissionOut]:
    """Every permission this product defines (used when building custom roles)."""
    catalog: dict[str, str] = request.app.state.product_roles.catalog
    return [PermissionOut(name=name, description=text) for name, text in sorted(catalog.items())]
