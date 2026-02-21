"""FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.db.engine import get_db

# Re-export get_db for convenience
__all__ = ["get_db", "get_settings_dep"]


@lru_cache
def get_settings_dep() -> Settings:
    return get_settings()
