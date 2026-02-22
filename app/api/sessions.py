from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth_or_tenant, get_company_db_flexible
from app.services.auth import AuthContext
from app.schemas import SessionCreate, SessionRead

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/properties/{property_id}/sessions", response_model=SessionRead, status_code=201)
async def create_session(
    property_id: str,
    body: SessionCreate,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    if body.type not in ("move_in", "move_out"):
        raise HTTPException(400, "type must be 'move_in' or 'move_out'")
    sess = await crud.create_session(db, property_id, body.type, body.tenant_name)
    return sess


@router.get("/properties/{property_id}/sessions", response_model=list[SessionRead])
async def list_sessions(
    property_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    return await crud.list_sessions_for_property(db, property_id)


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    sess = await crud.get_session(db, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess


@router.put("/sessions/{session_id}/status")
async def update_session_status(
    session_id: str,
    body: dict,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    """Update session report_status (e.g. tenant finishes review -> pending_review)."""
    sess = await crud.get_session(db, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    new_status = body.get("report_status")
    if new_status not in ("pending_review", "submitted"):
        raise HTTPException(400, "Invalid status")
    if sess.report_status in ("published",):
        raise HTTPException(409, "Session already published")
    sess.report_status = new_status
    await db.commit()
    return {"ok": True, "report_status": new_status}
