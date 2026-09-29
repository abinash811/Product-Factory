"""Version 1 of the public API. Every product feature router is included here."""

from fastapi import APIRouter

from app.core.errors import COMMON_ERRORS

api_router = APIRouter(responses=COMMON_ERRORS)

# Feature routers are added here as they are built, e.g.:
#   api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
