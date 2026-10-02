"""The tenant-scoped repository: the ONLY way product code reads or writes tenant-owned tables.

Every query is automatically limited to one organization, so a forgotten filter cannot leak data.
Looking up a row from another organization simply finds nothing (the caller answers 404).
Postgres row-level security (build step 3c) is a second, independent lock on the same rule.
"""

import math
import uuid
from typing import Any, Protocol

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.pagination import PageData, PageParams


class OrganizationOwned(Protocol):
    id: Any
    organization_id: Any


class TenantRepository[T: OrganizationOwned]:
    model: type[T]
    not_found_message = "Not found."

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    def select(self) -> Select[T]:
        """Start every query from here: it is already limited to this organization."""
        return select(self.model).where(self.model.organization_id == self.organization_id)

    async def get(self, item_id: uuid.UUID) -> T | None:
        return (await self.session.scalars(self.select().where(self.model.id == item_id))).first()

    async def get_or_404(self, item_id: uuid.UUID) -> T:
        item = await self.get(item_id)
        if item is None:
            raise NotFoundError(self.not_found_message)
        return item

    async def paginate(self, statement: Select[T], params: PageParams) -> PageData[T]:
        total = (
            await self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        rows = (
            (await self.session.scalars(statement.limit(params.page_size).offset(params.offset)))
            .unique()
            .all()
        )
        pages = math.ceil(total / params.page_size)
        return PageData(
            items=list(rows), total=total, page=params.page, page_size=params.page_size, pages=pages
        )

    def add(self, item: T) -> T:
        """Attach a new row to this organization (a mismatching organization is refused)."""
        if getattr(item, "organization_id", None) not in (None, self.organization_id):
            raise ValueError("Row belongs to a different organization.")
        item.organization_id = self.organization_id
        self.session.add(item)
        return item

    async def delete(self, item: T) -> None:
        if item.organization_id != self.organization_id:
            raise ValueError("Row belongs to a different organization.")
        await self.session.delete(item)
