"""Tenant link creation and management."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import crud


async def create_link_for_session(
    db: AsyncSession, session_id: str, duration_days: int = 7
) -> str:
    """Create a new tenant link for a session. Returns the token."""
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
    await crud.create_tenant_link(db, session_id, token, expires_at)
    return token


async def deactivate_links_for_session(db: AsyncSession, session_id: str) -> None:
    """Deactivate all active links for a session."""
    session = await crud.get_session(db, session_id)
    if session and session.tenant_links:
        for link in session.tenant_links:
            if link.is_active:
                link.is_active = False
        await db.commit()
