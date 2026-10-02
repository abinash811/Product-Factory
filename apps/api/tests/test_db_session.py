"""Per-request session behaviour, using real commits on a scratch table dropped afterwards."""

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import SessionDep
from app.core.errors import ConflictError
from tests.conftest import TEST_DATABASE_URL
from tests.db_models import ScratchBase, Widget

router = APIRouter(prefix="/_d")
Session = SessionDep


class WidgetOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: str
    updated_at: str


def _out(w: Widget) -> WidgetOut:
    return WidgetOut(
        id=w.id,
        name=w.name,
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    )


@router.post("/widgets")
async def _create(name: str, session: Session) -> WidgetOut:
    widget = Widget(name=name)
    session.add(widget)
    await session.flush()
    await session.refresh(widget)
    return _out(widget)


@router.post("/widgets-then-fail")
async def _create_then_fail(name: str, session: Session) -> None:
    session.add(Widget(name=name))
    await session.flush()
    raise ConflictError("Stopped after writing.")


@router.patch("/widgets/{widget_id}")
async def _rename(widget_id: uuid.UUID, name: str, session: Session) -> WidgetOut:
    widget = await session.get_one(Widget, widget_id)
    widget.name = name
    await session.flush()
    await session.refresh(widget)
    return _out(widget)


@router.get("/count")
async def _count(session: Session) -> int:
    return (await session.scalar(select(func.count()).select_from(Widget))) or 0


async def _ddl(action: str) -> None:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as connection:
        if action == "create":
            await connection.run_sync(ScratchBase.metadata.drop_all)
        await connection.run_sync(getattr(ScratchBase.metadata, f"{action}_all"))
    await engine.dispose()


@pytest.fixture
def widgets_client(app: FastAPI) -> Iterator[TestClient]:
    asyncio.run(_ddl("create"))
    app.include_router(router)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        asyncio.run(_ddl("drop"))


def test_successful_request_is_committed(widgets_client: TestClient) -> None:
    assert widgets_client.post("/_d/widgets", params={"name": "kept"}).status_code == 200
    assert widgets_client.get("/_d/count").json() == 1  # a different request sees it


def test_failed_request_is_rolled_back(widgets_client: TestClient) -> None:
    response = widgets_client.post("/_d/widgets-then-fail", params={"name": "lost"})
    assert response.status_code == 409
    assert widgets_client.get("/_d/count").json() == 0


def test_a_failed_commit_is_an_error_not_a_success(
    widgets_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_commit(self: AsyncSession) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(AsyncSession, "commit", broken_commit)
    response = widgets_client.post("/_d/widgets", params={"name": "doomed"})
    assert response.status_code == 500  # the client must never be told 'created' when it was not
    monkeypatch.undo()
    assert widgets_client.get("/_d/count").json() == 0


def test_updated_at_moves_forward_on_update(widgets_client: TestClient) -> None:
    created = widgets_client.post("/_d/widgets", params={"name": "old"}).json()
    renamed = widgets_client.patch(f"/_d/widgets/{created['id']}", params={"name": "new"}).json()
    assert renamed["created_at"] == created["created_at"]
    assert renamed["updated_at"] > created["updated_at"]
