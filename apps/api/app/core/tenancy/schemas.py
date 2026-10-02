"""Request and response shapes for organizations, roles and members."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
