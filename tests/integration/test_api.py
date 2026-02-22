"""Integration tests for API endpoints."""

from __future__ import annotations

import io
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.auth_models import AuthBase, Company, User, UserSession
from app.main import app
from app.db import engine as engine_module
from app.db import auth_engine as auth_engine_module
from app.services.auth import hash_password, _hash_token, AuthContext, SESSION_COOKIE_NAME


# Raw session token for the test user
_TEST_TOKEN = "test-session-token-abc123"
_TEST_COMPANY_ID = "01TESTCOMPANY000"


@pytest_asyncio.fixture
async def client():
    """Create a test client with in-memory auth + tenant databases."""
    # --- Auth DB (in-memory) ---
    test_auth_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    test_auth_factory = async_sessionmaker(test_auth_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

    # Seed company + admin user + session
    async with test_auth_factory() as db:
        company = Company(id=_TEST_COMPANY_ID, name="Test Co", slug="test-co")
        db.add(company)
        await db.flush()

        admin = User(
            company_id=company.id,
            email="admin@test.com",
            display_name="Admin",
            password_hash=hash_password("testpass123"),
            role="admin",
        )
        db.add(admin)
        await db.flush()

        from datetime import datetime, timezone, timedelta
        session = UserSession(
            user_id=admin.id,
            token_hash=_hash_token(_TEST_TOKEN),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            ip_address="127.0.0.1",
        )
        db.add(session)
        await db.commit()

    # Override auth DB dependency
    async def override_get_auth_db():
        async with test_auth_factory() as session:
            yield session

    from app.db.auth_engine import get_auth_db
    app.dependency_overrides[get_auth_db] = override_get_auth_db

    # --- Tenant DB (in-memory) ---
    test_tenant_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    test_tenant_factory = async_sessionmaker(test_tenant_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_tenant_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default company settings
    async with test_tenant_factory() as db:
        from app.db import crud
        await crud.create_company_settings(db)

    # Override tenant DB: make tenant_pool always return our test factory
    from unittest.mock import MagicMock
    original_session_factory = engine_module.tenant_pool.session_factory

    def mock_session_factory(company_id):
        return test_tenant_factory

    engine_module.tenant_pool.session_factory = mock_session_factory

    # Also override get_db for any legacy usage
    async def override_get_db():
        async with test_tenant_factory() as session:
            yield session

    from app.db.engine import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={SESSION_COOKIE_NAME: _TEST_TOKEN},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    engine_module.tenant_pool.session_factory = original_session_factory
    await test_auth_engine.dispose()
    await test_tenant_engine.dispose()


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
