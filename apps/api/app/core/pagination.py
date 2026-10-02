"""Shared pagination and sorting so every list endpoint behaves the same way.

Usage in a route:
    params: Annotated[PageParams, Depends(page_params)]
    sort: Annotated[list[SortField], Depends(sorting(["name", "created_at"], "-created_at"))]
Filtering stays explicit per endpoint: declare each allowed filter as its own typed query parameter.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from app.core.errors import BadRequestError

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        pages = math.ceil(total / params.page_size) if total else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=pages,
        )


@dataclass(frozen=True)
class PageData[T]:
    """One page of database rows, as returned by repositories (not an API response)."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def map_page[A, B](page: PageData[A], convert: Callable[[A], B]) -> Page[B]:
    """Same page, different item type (for example database rows into response models)."""
    return Page[B](
        items=[convert(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        pages=page.pages,
    )


class SortField(BaseModel):
    field: str
    descending: bool = False


def parse_sort(raw: str | None, allowed: Sequence[str], default: str) -> list[SortField]:
    """Parse "name,-created_at" into fields, accepting only allow-listed names."""
    fields: list[SortField] = []
    for raw_part in (raw or default).split(","):
        part = raw_part.strip()
        if not part:
            continue
        descending = part.startswith("-")
        name = part.lstrip("-+")
        if name not in allowed:
            raise BadRequestError(
                f"Cannot sort by '{name}'. Allowed: {', '.join(allowed)}.",
                code="invalid_sort",
            )
        fields.append(SortField(field=name, descending=descending))
    return fields


def sorting(allowed: Sequence[str], default: str) -> Callable[..., list[SortField]]:
    hint = f"Comma-separated, '-' prefix = descending. Allowed: {', '.join(allowed)}"

    def dependency(sort: Annotated[str | None, Query(description=hint)] = None) -> list[SortField]:
        return parse_sort(sort, allowed, default)

    return dependency
