"""Version 1 of the public API. Every product feature router is included here."""

from fastapi import APIRouter

from app.api.v1 import invitations, me, members, organizations, permissions, roles
from app.core.errors import COMMON_ERRORS

api_router = APIRouter(responses=COMMON_ERRORS)

api_router.include_router(me.router)
api_router.include_router(permissions.router)
api_router.include_router(organizations.router)
api_router.include_router(roles.router)
api_router.include_router(members.router)
api_router.include_router(invitations.org_router)
api_router.include_router(invitations.accept_router)
# Product feature routers are added below, e.g.:
#   api_router.include_router(invoices.router)  # with prefix "/organizations/{org_id}/invoices"
