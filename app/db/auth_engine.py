"""Auth DB engine and session factory for the central auth.db."""

from __future__ import annotations

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()

_auth_db_path = Path(_settings.auth_database_url.replace("sqlite+aiosqlite:///", ""))
_auth_db_path.parent.mkdir(parents=True, exist_ok=True)

auth_engine = create_async_engine(_settings.auth_database_url, echo=False)
auth_session_factory = async_sessionmaker(auth_engine, class_=AsyncSession, expire_on_commit=False)


async def get_auth_db():
    """FastAPI dependency that yields an async session to the central auth DB."""
    async with auth_session_factory() as session:
        yield session
