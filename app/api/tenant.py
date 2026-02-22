"""Tenant token-validated API endpoints.

Token format: {company_id}:{random_token}
The company_id prefix routes to the correct tenant DB.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.engine import tenant_pool

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


def _parse_token(token: str) -> tuple[str, str]:
    """Split {company_id}:{random_token}. Returns (company_id, full_token)."""
    if ":" not in token:
        raise HTTPException(400, "Invalid token format")
    company_id = token.split(":", 1)[0]
    return company_id, token


async def _get_tenant_db(company_id: str):
    """Get an async session for the tenant DB."""
    factory = tenant_pool.session_factory(company_id)
    async with factory() as session:
        yield session


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
async def get_tenant_session(token: str = Query(...)):
    """Get session info for a tenant link token."""
    company_id, full_token = _parse_token(token)
    factory = tenant_pool.session_factory(company_id)
    async with factory() as db:
        link, session = await _validate_token(full_token, db)
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
            "company_id": company_id,
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
async def get_tenant_rooms(token: str = Query(...)):
    """Get room templates for the property linked to this token."""
    company_id, full_token = _parse_token(token)
    factory = tenant_pool.session_factory(company_id)
    async with factory() as db:
        link, session = await _validate_token(full_token, db)
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
