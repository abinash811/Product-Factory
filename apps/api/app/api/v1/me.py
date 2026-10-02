from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.auth.dependencies import get_current_user
from app.core.auth.models import User
from app.core.db import SessionDep
from app.core.tenancy.models import Membership, Organization
from app.core.tenancy.schemas import MeOrganization, MeOut, RoleRef

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> MeOut:
    """The signed-in user and every organization they belong to, with their role in each."""
    statement = (
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    )
    rows = (await session.execute(statement)).unique().all()
    return MeOut(
        id=user.id,
        email=user.email,
        organizations=[
            MeOrganization(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role=RoleRef.model_validate(membership.role),
            )
            for membership, org in rows
        ],
    )
