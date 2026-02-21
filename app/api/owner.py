"""Owner dashboard + management API endpoints."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud
from app.services.auth import get_current_owner
from app.services.encryption import encrypt_value, decrypt_value
from app.schemas.owner_settings import OwnerSettingsRead, OwnerSettingsUpdate
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.session import SessionRead
from app.schemas.tenant_link import TenantLinkCreate, TenantLinkRead
from app.schemas.candidate import CandidateOwnerUpdate, CandidateRead

router = APIRouter(prefix="/api/owner", tags=["owner"])


# ── Queue ────────────────────────────────────────────────

@router.get("/queue")
async def owner_queue(
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Return pending inspections (active) and pending review sessions."""
    from app.models import Property, Session
    from sqlalchemy import select

    # Get all properties for this owner
    result = await db.execute(
        select(Property).where(Property.owner_id == owner_id)
    )
    properties = list(result.scalars().all())
    prop_ids = [p.id for p in properties]

    if not prop_ids:
        return {"pending_inspections": [], "pending_review": []}

    # Get sessions with relevant statuses
    result = await db.execute(
        select(Session).where(
            Session.property_id.in_(prop_ids),
            Session.report_status.in_(["active", "pending_review", "submitted"]),
        )
    )
    sessions = list(result.scalars().all())

    prop_map = {p.id: p for p in properties}
    pending_inspections = []
    pending_review = []

    for s in sessions:
        prop = prop_map.get(s.property_id)
        item = {
            "session_id": s.id,
            "property_id": s.property_id,
            "property_label": prop.label if prop else "",
            "property_address": prop.address if prop else "",
            "tenant_name": s.tenant_name,
            "tenant_name_2": s.tenant_name_2,
            "session_type": s.type,
            "report_status": s.report_status,
            "review_flag": s.review_flag,
            "created_at": s.created_at.isoformat(),
            "room_count": len(s.captures) if s.captures else 0,
        }
        if s.report_status == "active":
            pending_inspections.append(item)
        else:
            pending_review.append(item)

    return {"pending_inspections": pending_inspections, "pending_review": pending_review}


# ── Properties ───────────────────────────────────────────

@router.get("/properties")
async def list_owner_properties(
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Property
    from sqlalchemy import select
    result = await db.execute(
        select(Property).where(Property.owner_id == owner_id).order_by(Property.created_at.desc())
    )
    properties = list(result.scalars().all())
    return [
        {
            "id": p.id,
            "label": p.label,
            "address": p.address,
            "rooms": p.rooms,
            "created_at": p.created_at.isoformat(),
            "room_template_count": len(p.room_templates) if p.room_templates else 0,
            "session_count": len(p.sessions) if p.sessions else 0,
        }
        for p in properties
    ]


@router.post("/properties")
async def create_owner_property(
    body: PropertyCreate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    prop = await crud.create_property(db, body.label, body.rooms)
    prop.address = body.address
    prop.owner_id = owner_id
    await db.commit()
    await db.refresh(prop)
    return PropertyRead.model_validate(prop)


@router.get("/properties/{property_id}")
async def get_owner_property(
    property_id: str,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Property not found")

    room_templates = await crud.list_room_templates_for_property(db, property_id)
    sessions = await crud.list_sessions_for_property(db, property_id)

    return {
        "id": prop.id,
        "label": prop.label,
        "address": prop.address,
        "rooms": prop.rooms,
        "created_at": prop.created_at.isoformat(),
        "room_templates": [
            {
                "id": rt.id,
                "name": rt.name,
                "display_order": rt.display_order,
                "positions": rt.positions,
                "created_at": rt.created_at.isoformat(),
            }
            for rt in room_templates
        ],
        "sessions": [
            {
                "id": s.id,
                "type": s.type,
                "tenant_name": s.tenant_name,
                "tenant_name_2": s.tenant_name_2,
                "report_status": s.report_status,
                "review_flag": s.review_flag,
                "created_at": s.created_at.isoformat(),
                "room_count": len(s.captures) if s.captures else 0,
            }
            for s in sessions
        ],
    }


@router.put("/properties/{property_id}")
async def update_owner_property(
    property_id: str,
    body: dict,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Property not found")
    if "address" in body:
        prop.address = body["address"]
    if "label" in body:
        prop.label = body["label"]
    await db.commit()
    await db.refresh(prop)
    return PropertyRead.model_validate(prop)


# ── Sessions (create via tenant link) ────────────────────

@router.post("/properties/{property_id}/sessions")
async def create_session_with_link(
    property_id: str,
    body: TenantLinkCreate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Create a session + tenant link for a property."""
    prop = await crud.get_property(db, property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Property not found")

    # Create session
    session = await crud.create_session(
        db, property_id, body.session_type, body.tenant_name,
    )
    session.tenant_name_2 = body.tenant_name_2
    session.report_status = "active"
    await db.commit()
    await db.refresh(session)

    # Create tenant link
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.duration_days)
    link = await crud.create_tenant_link(db, session.id, token, expires_at)

    return {
        "session": SessionRead.model_validate(session),
        "link": TenantLinkRead.model_validate(link),
        "url": f"/inspect/{token}",
    }


# ── Session actions ──────────────────────────────────────

@router.post("/sessions/{session_id}/reactivate")
async def reactivate_session(
    session_id: str,
    body: dict,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a session with a new tenant link."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    prop = await crud.get_property(db, session.property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Session not found")

    duration_days = body.get("duration_days", 7)
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

    # Deactivate existing links
    if session.tenant_links:
        for existing in session.tenant_links:
            if existing.is_active:
                existing.is_active = False

    session.report_status = "active"
    session.review_flag = None
    await db.commit()

    link = await crud.create_tenant_link(db, session.id, token, expires_at)

    return {
        "session_id": session.id,
        "link": TenantLinkRead.model_validate(link),
        "url": f"/inspect/{token}",
    }


@router.post("/sessions/{session_id}/publish")
async def publish_session(
    session_id: str,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Publish a reviewed session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    prop = await crud.get_property(db, session.property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Session not found")

    session.report_status = "published"

    # Deactivate any active tenant links
    if session.tenant_links:
        for link in session.tenant_links:
            if link.is_active:
                link.is_active = False

    await db.commit()
    return {"ok": True, "session_id": session.id, "report_status": "published"}


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a session and deactivate its tenant links."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    prop = await crud.get_property(db, session.property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Session not found")

    session.report_status = "cancelled"

    # Deactivate any active tenant links
    if session.tenant_links:
        for link in session.tenant_links:
            if link.is_active:
                link.is_active = False

    await db.commit()
    return {"ok": True, "session_id": session.id, "report_status": "cancelled"}


# ── Owner candidate review ──────────────────────────────

@router.put("/candidates/{candidate_id}")
async def owner_update_candidate(
    candidate_id: str,
    body: CandidateOwnerUpdate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    cand = await crud.get_candidate(db, candidate_id)
    if not cand:
        raise HTTPException(404, "Candidate not found")

    updates = {}
    if body.owner_accepted is not None:
        updates["owner_accepted"] = body.owner_accepted
    if body.repair_cost is not None:
        updates["repair_cost"] = body.repair_cost
    if body.owner_notes is not None:
        updates["owner_notes"] = body.owner_notes

    if updates:
        cand = await crud.update_candidate(db, cand, **updates)
    return CandidateRead.model_validate(cand)


# ── Settings ─────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    settings = await crud.get_owner_settings(db, owner_id)
    if not settings:
        settings = await crud.create_owner_settings(db, owner_id)

    return {
        "id": settings.id,
        "owner_id": settings.owner_id,
        "llm_provider": settings.llm_provider,
        "openai_api_key_set": bool(settings.openai_api_key),
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "gemini_api_key_set": bool(settings.gemini_api_key),
        "grok_api_key_set": bool(settings.grok_api_key),
        "default_link_days": settings.default_link_days,
    }


@router.put("/settings")
async def update_settings(
    body: OwnerSettingsUpdate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    settings = await crud.get_owner_settings(db, owner_id)
    if not settings:
        settings = await crud.create_owner_settings(db, owner_id)

    updates = {}
    if body.llm_provider is not None:
        updates["llm_provider"] = body.llm_provider
    if body.default_link_days is not None:
        updates["default_link_days"] = body.default_link_days

    # Encrypt API keys before storing
    for key_field in ("openai_api_key", "anthropic_api_key", "gemini_api_key", "grok_api_key"):
        val = getattr(body, key_field, None)
        if val is not None:
            try:
                updates[key_field] = encrypt_value(val) if val else ""
            except RuntimeError:
                # FERNET_KEY not set — store plain (dev mode)
                updates[key_field] = val

    if updates:
        settings = await crud.update_owner_settings(db, settings, **updates)

    return {
        "id": settings.id,
        "owner_id": settings.owner_id,
        "llm_provider": settings.llm_provider,
        "openai_api_key_set": bool(settings.openai_api_key),
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "gemini_api_key_set": bool(settings.gemini_api_key),
        "grok_api_key_set": bool(settings.grok_api_key),
        "default_link_days": settings.default_link_days,
    }


# ── PDF Generation ───────────────────────────────────────

@router.post("/sessions/{session_id}/pdf")
async def generate_session_pdf(
    session_id: str,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF report for a session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    prop = await crud.get_property(db, session.property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Session not found")

    from app.services.pdf_generator import generate_pdf
    pdf_bytes = await generate_pdf(db, session_id)

    filename = f"inspection_report_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Report search ────────────────────────────────────────

@router.get("/reports/search")
async def search_reports(
    q: str = "",
    session_type: str = "",
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    """Search published reports by tenant name or filter by type."""
    from app.models import Property, Session
    from sqlalchemy import select

    query = select(Session).join(Property).where(
        Property.owner_id == owner_id,
        Session.report_status == "published",
    )

    if session_type:
        query = query.where(Session.type == session_type)

    result = await db.execute(query.order_by(Session.created_at.desc()))
    sessions = list(result.scalars().all())

    # Filter by search term (tenant name)
    if q:
        q_lower = q.lower()
        sessions = [
            s for s in sessions
            if q_lower in (s.tenant_name or "").lower()
            or q_lower in (s.tenant_name_2 or "").lower()
        ]

    # Fetch properties for display
    prop_ids = list({s.property_id for s in sessions})
    props = {}
    for pid in prop_ids:
        p = await crud.get_property(db, pid)
        if p:
            props[pid] = p

    return [
        {
            "session_id": s.id,
            "property_id": s.property_id,
            "property_label": props[s.property_id].label if s.property_id in props else "",
            "property_address": props[s.property_id].address if s.property_id in props else "",
            "tenant_name": s.tenant_name,
            "tenant_name_2": s.tenant_name_2,
            "session_type": s.type,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]
