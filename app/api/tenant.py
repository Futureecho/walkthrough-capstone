"""Tenant token-validated API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


async def _validate_token(token: str, db: AsyncSession):
    """Validate tenant link token and return (link, session)."""
    link = await crud.get_tenant_link_by_token(db, token)
    if not link:
        raise HTTPException(404, "Invalid or expired link")
    if not link.is_active:
        raise HTTPException(410, "Link has been deactivated")
    if link.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(410, "Link has expired")

    session = await crud.get_session(db, link.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return link, session


@router.get("/session")
async def get_tenant_session(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get session info for a tenant link token."""
    link, session = await _validate_token(token, db)
    prop = await crud.get_property(db, session.property_id)

    room_templates = await crud.list_room_templates_for_property(db, session.property_id)

    return {
        "session_id": session.id,
        "property_id": session.property_id,
        "property_label": prop.label if prop else "",
        "property_address": prop.address if prop else "",
        "session_type": session.type,
        "tenant_name": session.tenant_name,
        "report_status": session.report_status,
        "room_templates": [
            {
                "id": rt.id,
                "name": rt.name,
                "display_order": rt.display_order,
                "positions": rt.positions,
            }
            for rt in room_templates
        ],
        "captures": [
            {
                "id": c.id,
                "room": c.room,
                "status": c.status,
            }
            for c in (session.captures or [])
        ],
        "expires_at": link.expires_at.isoformat(),
    }


@router.get("/rooms")
async def get_tenant_rooms(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get room templates for the property linked to this token."""
    link, session = await _validate_token(token, db)
    room_templates = await crud.list_room_templates_for_property(db, session.property_id)

    return [
        {
            "id": rt.id,
            "name": rt.name,
            "display_order": rt.display_order,
            "positions": rt.positions,
        }
        for rt in room_templates
    ]
