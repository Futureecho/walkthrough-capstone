"""Concern API — tenant capture + owner listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, require_auth_or_tenant, get_company_db, get_company_db_flexible
from app.services.image_store import save_image

router = APIRouter(tags=["concerns"])


# ── Tenant endpoints ─────────────────────────────────────

@router.post("/api/tenant/concerns", status_code=201)
async def create_concern(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    session_id: str = Form(...),
    room: str = Form(""),
    token: str = Form(""),
    auth=Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    session = await crud.get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Save image using existing pattern — use session_id as the "capture_id" bucket
    data = await file.read()
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[1].lower()

    # Use a concerns subfolder keyed by session
    bucket = f"concerns_{session_id}"
    existing = await crud.list_concerns_for_session(db, session_id)
    seq = len(existing) + 1

    orig_path, thumb_path = await save_image(data, bucket, seq, ext, company_id=auth.company_id)

    concern = await crud.create_concern(
        db,
        session_id=session_id,
        room=room,
        title=title[:50],
        description=description[:200],
        file_path=orig_path,
        thumbnail_path=thumb_path,
    )

    return {
        "id": concern.id,
        "title": concern.title,
        "description": concern.description,
        "room": concern.room,
        "thumbnail_path": concern.thumbnail_path,
    }


@router.get("/api/tenant/concerns")
async def list_tenant_concerns(
    session_id: str = Query(...),
    token: str = Query(""),
    auth=Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    concerns = await crud.list_concerns_for_session(db, session_id)
    return [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "room": c.room,
            "thumbnail_path": c.thumbnail_path,
            "created_at": c.created_at.isoformat(),
        }
        for c in concerns
    ]


# ── Owner endpoints ──────────────────────────────────────

@router.get("/api/owner/sessions/{session_id}/concerns")
async def list_owner_concerns(
    session_id: str,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    concerns = await crud.list_concerns_for_session(db, session_id)
    return [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "room": c.room,
            "file_path": c.file_path,
            "thumbnail_path": c.thumbnail_path,
            "created_at": c.created_at.isoformat(),
        }
        for c in concerns
    ]
