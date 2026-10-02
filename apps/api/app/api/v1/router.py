"""Version 1 of the public API. Every product feature router is included here."""

from fastapi import APIRouter, Depends

from app.api.v1 import invitations, me, members, organizations, permissions, roles
from app.core.auth.dependencies import get_identity
from app.core.errors import COMMON_ERRORS

# Every route under /api/v1 requires a valid login by default. A genuinely public route must be
# mounted outside this router, on purpose, and listed in tests/test_app_contracts.py.
api_router = APIRouter(responses=COMMON_ERRORS, dependencies=[Depends(get_identity)])

api_router.include_router(me.router)
api_router.include_router(permissions.router)
api_router.include_router(organizations.router)
api_router.include_router(roles.router)
api_router.include_router(members.router)
api_router.include_router(invitations.org_router)
api_router.include_router(invitations.accept_router)
# Product feature routers are added below, e.g.:
#   api_router.include_router(invoices.router)  # with prefix "/organizations/{org_id}/invoices"
