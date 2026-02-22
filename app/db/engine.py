"""Async SQLAlchemy engine and session factory — tenant engine pool."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine

from app.config import get_settings

_settings = get_settings()

# Legacy single-DB engine (kept for migration only)
_db_path = _settings.database_url.replace("sqlite+aiosqlite:///", "")
Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(_settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency that yields an async DB session (legacy single-DB)."""
    async with async_session_factory() as session:
        yield session


# ── Tenant Engine Pool ────────────────────────────────────

_MAX_CACHED_ENGINES = 20


class TenantEnginePool:
    """LRU cache of per-company async engines.

    Each company gets its own SQLite DB at:
        data/companies/{company_id}/tenant.db
    """

    def __init__(self, max_size: int = _MAX_CACHED_ENGINES):
        self._engines: OrderedDict[str, AsyncEngine] = OrderedDict()
        self._max_size = max_size

    def _db_url(self, company_id: str) -> str:
        return f"sqlite+aiosqlite:///data/companies/{company_id}/tenant.db"

    def _db_path(self, company_id: str) -> Path:
        return Path(f"data/companies/{company_id}/tenant.db")

    def get_engine(self, company_id: str) -> AsyncEngine:
        """Get or create an async engine for a company, with LRU eviction."""
        if company_id in self._engines:
            self._engines.move_to_end(company_id)
            return self._engines[company_id]

        # Ensure directory exists
        self._db_path(company_id).parent.mkdir(parents=True, exist_ok=True)

        eng = create_async_engine(self._db_url(company_id), echo=False)
        self._engines[company_id] = eng

        # Evict oldest if over capacity
        if len(self._engines) > self._max_size:
            _, old_engine = self._engines.popitem(last=False)
            # Schedule disposal (non-blocking)
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(old_engine.dispose())
            except RuntimeError:
                pass  # No running loop — disposal will happen on GC

        return eng

    def session_factory(self, company_id: str) -> async_sessionmaker[AsyncSession]:
        eng = self.get_engine(company_id)
        return async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    async def dispose_all(self):
        """Dispose all cached engines (for shutdown)."""
        for eng in self._engines.values():
            await eng.dispose()
        self._engines.clear()


tenant_pool = TenantEnginePool()


def get_tenant_engine(company_id: str) -> AsyncEngine:
    """Get the async engine for a specific company's tenant DB."""
    return tenant_pool.get_engine(company_id)


async def create_tenant_db(company_id: str):
    """Create all tenant tables for a new company."""
    from app.models.base import Base

    eng = tenant_pool.get_engine(company_id)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
