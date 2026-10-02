"""Request and response shapes for organizations, roles and members."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")]
Grant = Annotated[str, StringConstraints(max_length=100)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrganizationOut(ORM):
    id: uuid.UUID
    name: str
    slug: str


class OrganizationCreate(BaseModel):
    name: Name
    slug: Slug | None = None


class OrganizationUpdate(BaseModel):
    name: Name


class RoleRef(ORM):
    id: uuid.UUID
    key: str | None
    name: str


class RoleOut(RoleRef):
    description: str
    permissions: list[str]
    is_system: bool


class RoleCreate(BaseModel):
    name: Name
    description: Annotated[str, Field(max_length=300)] = ""
    permissions: Annotated[list[Grant], Field(max_length=100)]


class RoleUpdate(BaseModel):
    name: Name | None = None
    description: Annotated[str, Field(max_length=300)] | None = None
    permissions: Annotated[list[Grant], Field(max_length=100)] | None = None


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None
    role: RoleRef
    created_at: datetime


class MemberUpdate(BaseModel):
    role_id: uuid.UUID


class MeOrganization(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: RoleRef


class MeOut(BaseModel):
    id: uuid.UUID
    email: str | None
    organizations: list[MeOrganization]


class PermissionOut(BaseModel):
    name: str
    description: str


class InvitationCreate(BaseModel):
    email: EmailStr
    role_id: uuid.UUID
    expires_in_days: Annotated[int, Field(ge=1, le=30)] = 7


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleRef
    status: Literal["pending", "accepted", "expired"]
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationCreated(InvitationOut):
    # Shown ONCE, at creation. Email delivery is added in build steps 5-6; until then the
    # inviter passes this to the invitee (for example as a link).
    token: str


class InvitationAccept(BaseModel):
    token: Annotated[str, StringConstraints(min_length=20, max_length=200)]


class InvitationAccepted(BaseModel):
    organization: OrganizationOut
    role: RoleRef
