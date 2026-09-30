import uuid
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.conftest import TEST_DATABASE_URL
from tests.db_models import Widget


async def test_new_rows_get_a_uuid_and_utc_timestamps(db_session: AsyncSession) -> None:
    widget = Widget(name="first")
    db_session.add(widget)
    await db_session.flush()
    await db_session.refresh(widget)
    assert isinstance(widget.id, uuid.UUID)
    assert widget.created_at.tzinfo is not None
    assert widget.created_at.utcoffset() == timedelta(0)
    assert widget.updated_at >= widget.created_at


async def test_ids_are_unique_random_values(db_session: AsyncSession) -> None:
    db_session.add_all([Widget(name="a"), Widget(name="b")])
    await db_session.flush()
    ids = (await db_session.scalars(select(Widget.id))).all()
    assert len(set(ids)) == 2


async def test_constraint_names_follow_the_naming_convention(db_session: AsyncSession) -> None:
    names = (
        await db_session.scalars(
            text("SELECT conname FROM pg_constraint WHERE conrelid = 'test_widgets'::regclass")
        )
    ).all()
    assert set(names) == {"pk_test_widgets", "uq_test_widgets_name"}


async def test_work_inside_a_test_is_invisible_outside_it(db_session: AsyncSession) -> None:
    db_session.add(Widget(name="private"))
    await db_session.flush()
    other = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with other.connect() as connection:
            exists = await connection.scalar(text("SELECT to_regclass('test_widgets')"))
        assert exists is None  # nothing was committed, so the next test starts clean
    finally:
        await other.dispose()
