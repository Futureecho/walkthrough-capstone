import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.db import crud


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_create_and_get_property(db):
    prop = await crud.create_property(db, "456 Oak Ave", ["Living Room", "Kitchen"])
    assert prop.id is not None
    assert prop.label == "456 Oak Ave"

    fetched = await crud.get_property(db, prop.id)
    assert fetched is not None
    assert fetched.label == "456 Oak Ave"
    assert fetched.rooms == ["Living Room", "Kitchen"]


async def test_create_and_get_session(db):
    prop = await crud.create_property(db, "789 Pine Rd", ["Room A"])
    session_obj = await crud.create_session(db, prop.id, "move_in", "Jane Doe")
    assert session_obj.id is not None

    fetched = await crud.get_session(db, session_obj.id)
    assert fetched is not None
    assert fetched.property_id == prop.id
    assert fetched.type == "move_in"
    assert fetched.tenant_name == "Jane Doe"


async def test_create_and_update_capture(db):
    prop = await crud.create_property(db, "100 Elm St", ["Living Room"])
    session_obj = await crud.create_session(db, prop.id, "move_in")
    capture = await crud.create_capture(db, session_obj.id, "Living Room")
    assert capture.id is not None
    assert capture.room == "Living Room"

    updated = await crud.update_capture(db, capture, status="passed")
    assert updated.status == "passed"


async def test_create_capture_image_and_count(db):
    prop = await crud.create_property(db, "200 Maple Dr", ["Bedroom"])
    session_obj = await crud.create_session(db, prop.id, "move_in")
    capture = await crud.create_capture(db, session_obj.id, "Bedroom")

    await crud.create_capture_image(db, capture.id, 1, "/images/1/orig.jpg", "/images/1/thumb.jpg")
    await crud.create_capture_image(db, capture.id, 2, "/images/2/orig.jpg", "/images/2/thumb.jpg")

    count = await crud.count_images_for_capture(db, capture.id)
    assert count == 2
