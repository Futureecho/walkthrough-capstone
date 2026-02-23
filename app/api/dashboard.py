"""Dashboard + management API endpoints (replaces owner.py)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, require_role, get_company_db
from app.services.auth import AuthContext
from app.services.encryption import encrypt_value
from app.schemas.owner_settings import CompanySettingsUpdate
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.session import SessionRead
from app.schemas.tenant_link import TenantLinkCreate, TenantLinkRead
from app.schemas.candidate import CandidateOwnerUpdate, CandidateRead

router = APIRouter(prefix="/api/owner", tags=["dashboard"])


# ── Queue ────────────────────────────────────────────────

@router.get("/queue")
async def owner_queue(
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Return pending inspections (active) and pending review sessions."""
    from app.models import Property, Session
    from sqlalchemy import select

    result = await db.execute(select(Property).order_by(Property.created_at.desc()))
    properties = list(result.scalars().all())
    prop_ids = [p.id for p in properties]

    if not prop_ids:
        return {"pending_inspections": [], "pending_review": []}

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
            "concern_count": len(s.concerns) if s.concerns else 0,
        }
        if s.report_status == "active":
            pending_inspections.append(item)
        else:
            pending_review.append(item)

    return {"pending_inspections": pending_inspections, "pending_review": pending_review}


# ── Properties ───────────────────────────────────────────

@router.get("/properties")
async def list_owner_properties(
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    from app.models import Property
    from sqlalchemy import select
    result = await db.execute(
        select(Property).order_by(Property.created_at.desc())
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.create_property(db, body.label, body.rooms)
    prop.address = body.address
    await db.commit()
    await db.refresh(prop)
    return PropertyRead.model_validate(prop)


@router.get("/properties/{property_id}")
async def get_owner_property(
    property_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
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
                "capture_mode": rt.capture_mode,
                "active_ref_set_id": rt.active_ref_set_id,
                "created_at": rt.created_at.isoformat(),
                "reference_image_count": len(rt.reference_images) if rt.reference_images else 0,
                "reference_images": [
                    {
                        "id": img.id,
                        "set_id": img.set_id,
                        "position_hint": img.position_hint,
                        "thumbnail_url": "/" + img.thumbnail_path if img.thumbnail_path else None,
                    }
                    for img in (rt.reference_images or [])
                ],
                "reference_sets": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "capture_mode": s.capture_mode,
                        "image_count": s.image_count,
                        "is_active": rt.active_ref_set_id == s.id,
                        "created_at": s.created_at.isoformat(),
                        "images": [
                            {
                                "id": img.id,
                                "position_hint": img.position_hint,
                                "thumbnail_url": "/" + img.thumbnail_path if img.thumbnail_path else None,
                            }
                            for img in (s.images or [])
                        ],
                    }
                    for s in sorted(
                        (rt.reference_sets or []),
                        key=lambda s: s.created_at,
                        reverse=True,
                    )
                ],
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Create a session + tenant link for a property."""
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    session = await crud.create_session(
        db, property_id, body.session_type, body.tenant_name,
    )
    session.tenant_name_2 = body.tenant_name_2
    session.report_status = "active"
    await db.commit()
    await db.refresh(session)

    # Token format: {company_id}:{random} so tenant API can route to correct DB
    raw_token = secrets.token_urlsafe(48)
    token = f"{auth.company_id}:{raw_token}"
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Reactivate a session with a new tenant link."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    duration_days = body.get("duration_days", 7)
    raw_token = secrets.token_urlsafe(48)
    token = f"{auth.company_id}:{raw_token}"
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Publish a reviewed session."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    session.report_status = "published"

    if session.tenant_links:
        for link in session.tenant_links:
            if link.is_active:
                link.is_active = False

    await db.commit()
    return {"ok": True, "session_id": session.id, "report_status": "published"}


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Cancel a session and deactivate its tenant links."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    session.report_status = "cancelled"

    if session.tenant_links:
        for link in session.tenant_links:
            if link.is_active:
                link.is_active = False

    await db.commit()
    return {"ok": True, "session_id": session.id, "report_status": "cancelled"}


# ── Session work orders ─────────────────────────────────

@router.get("/sessions/{session_id}/work-orders")
async def list_session_work_orders(
    session_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    work_orders = await crud.list_work_orders_for_session(db, session_id)
    return [
        {
            "id": wo.id,
            "order_type": wo.order_type,
            "status": wo.status,
            "created_at": wo.created_at.isoformat(),
            "dispatched_at": wo.dispatched_at.isoformat() if wo.dispatched_at else None,
        }
        for wo in work_orders
    ]


# ── Owner candidate review ──────────────────────────────

@router.put("/candidates/{candidate_id}")
async def owner_update_candidate(
    candidate_id: str,
    body: CandidateOwnerUpdate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    settings = await crud.get_company_settings(db)
    if not settings:
        settings = await crud.create_company_settings(db)

    return {
        "id": settings.id,
        "llm_provider": settings.llm_provider,
        "openai_api_key_set": bool(settings.openai_api_key),
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "gemini_api_key_set": bool(settings.gemini_api_key),
        "grok_api_key_set": bool(settings.grok_api_key),
        "default_link_days": settings.default_link_days,
        "approval_email": settings.approval_email or "",
        "approval_email_set": bool(settings.approval_email),
    }


@router.put("/settings")
async def update_settings(
    body: CompanySettingsUpdate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    settings = await crud.get_company_settings(db)
    if not settings:
        settings = await crud.create_company_settings(db)

    updates = {}
    if body.llm_provider is not None:
        updates["llm_provider"] = body.llm_provider
    if body.default_link_days is not None:
        updates["default_link_days"] = body.default_link_days

    for key_field in ("openai_api_key", "anthropic_api_key", "gemini_api_key", "grok_api_key"):
        val = getattr(body, key_field, None)
        if val is not None:
            try:
                updates[key_field] = encrypt_value(val) if val else ""
            except RuntimeError:
                updates[key_field] = val

    if body.approval_email is not None:
        try:
            updates["approval_email"] = encrypt_value(body.approval_email) if body.approval_email else ""
        except RuntimeError:
            updates["approval_email"] = body.approval_email

    if updates:
        settings = await crud.update_company_settings(db, settings, **updates)

    return {
        "id": settings.id,
        "llm_provider": settings.llm_provider,
        "openai_api_key_set": bool(settings.openai_api_key),
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "gemini_api_key_set": bool(settings.gemini_api_key),
        "grok_api_key_set": bool(settings.grok_api_key),
        "default_link_days": settings.default_link_days,
        "approval_email": settings.approval_email or "",
        "approval_email_set": bool(settings.approval_email),
    }


# ── PDF Generation ───────────────────────────────────────

@router.post("/sessions/{session_id}/pdf")
async def generate_session_pdf(
    session_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Generate a PDF report for a session."""
    session = await crud.get_session(db, session_id)
    if not session:
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Search published reports by tenant name or filter by type."""
    from app.models import Session
    from sqlalchemy import select

    query = select(Session).where(Session.report_status == "published")

    if session_type:
        query = query.where(Session.type == session_type)

    result = await db.execute(query.order_by(Session.created_at.desc()))
    sessions = list(result.scalars().all())

    if q:
        q_lower = q.lower()
        sessions = [
            s for s in sessions
            if q_lower in (s.tenant_name or "").lower()
            or q_lower in (s.tenant_name_2 or "").lower()
        ]

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


# ── Data Export ───────────────────────────────────────────

@router.get("/export/full")
async def export_full(
    auth: AuthContext = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_company_db),
):
    """Export entire company data as ZIP (admin only)."""
    from app.services.export import export_full_zip
    zip_bytes = await export_full_zip(auth.company_id, db)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=company_export.zip"},
    )


@router.get("/export/property/{property_id}")
async def export_property(
    property_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Export a single property's data as ZIP."""
    from app.services.export import export_property_zip
    zip_bytes = await export_property_zip(auth.company_id, property_id, db)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=property_{property_id[:8]}.zip"},
    )


@router.get("/export/report/{session_id}")
async def export_report(
    session_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Export a session report as PDF."""
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    from app.services.export import export_pdf
    pdf_bytes = await export_pdf(session_id, db)

    filename = f"report_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
