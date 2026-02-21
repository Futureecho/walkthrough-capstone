"""Integration tests for API endpoints."""

from __future__ import annotations

import io
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.main import app
from app.db import engine as engine_module


@pytest_asyncio.fixture
async def client():
    """Create a test client with an in-memory database."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override the DB dependency
    original_engine = engine_module.engine
    original_factory = engine_module.async_session_factory
    engine_module.engine = test_engine
    engine_module.async_session_factory = test_factory

    async def override_get_db():
        async with test_factory() as session:
            yield session

    from app.db.engine import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    engine_module.engine = original_engine
    engine_module.async_session_factory = original_factory
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_property(client):
    r = await client.post("/api/properties", json={"label": "Test Unit", "rooms": ["Room A", "Room B"]})
    assert r.status_code == 201
    data = r.json()
    assert data["label"] == "Test Unit"
    assert data["rooms"] == ["Room A", "Room B"]
    prop_id = data["id"]

    r = await client.get(f"/api/properties/{prop_id}")
    assert r.status_code == 200
    assert r.json()["label"] == "Test Unit"


@pytest.mark.asyncio
async def test_list_properties(client):
    await client.post("/api/properties", json={"label": "A", "rooms": ["R1"]})
    await client.post("/api/properties", json={"label": "B", "rooms": ["R2"]})
    r = await client.get("/api/properties")
    assert r.status_code == 200
    assert len(r.json()) >= 2


@pytest.mark.asyncio
async def test_create_session(client):
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["R"]})
    prop_id = r.json()["id"]

    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "move_in", "tenant_name": "Jane"})
    assert r.status_code == 201
    data = r.json()
    assert data["type"] == "move_in"
    assert data["tenant_name"] == "Jane"


@pytest.mark.asyncio
async def test_create_session_invalid_type(client):
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["R"]})
    prop_id = r.json()["id"]

    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "invalid"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_capture(client):
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["Kitchen"]})
    prop_id = r.json()["id"]
    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "move_in"})
    session_id = r.json()["id"]

    r = await client.post("/api/captures", json={"session_id": session_id, "room": "Kitchen"})
    assert r.status_code == 201
    assert r.json()["room"] == "Kitchen"
    assert r.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_image(client, tmp_path):
    # Create property + session + capture
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["R"]})
    prop_id = r.json()["id"]
    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "move_in"})
    session_id = r.json()["id"]
    r = await client.post("/api/captures", json={"session_id": session_id, "room": "R"})
    capture_id = r.json()["id"]

    # Create a minimal JPEG
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    r = await client.post(
        f"/api/captures/{capture_id}/images",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        data={"orientation_hint": "center-from-door"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["seq"] == 1
    assert "file_path" in data


@pytest.mark.asyncio
async def test_capture_status(client):
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["R"]})
    prop_id = r.json()["id"]
    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "move_in"})
    session_id = r.json()["id"]
    r = await client.post("/api/captures", json={"session_id": session_id, "room": "R"})
    capture_id = r.json()["id"]

    r = await client.get(f"/api/captures/{capture_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["image_count"] == 0


@pytest.mark.asyncio
async def test_property_not_found(client):
    r = await client.get("/api/properties/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_submit_no_images(client):
    r = await client.post("/api/properties", json={"label": "P", "rooms": ["R"]})
    prop_id = r.json()["id"]
    r = await client.post(f"/api/properties/{prop_id}/sessions", json={"type": "move_in"})
    session_id = r.json()["id"]
    r = await client.post("/api/captures", json={"session_id": session_id, "room": "R"})
    capture_id = r.json()["id"]

    r = await client.post(f"/api/captures/{capture_id}/submit")
    assert r.status_code == 400
