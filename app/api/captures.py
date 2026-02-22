from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.engine import tenant_pool
from app.dependencies import require_auth_or_tenant, get_company_db_flexible
from app.services.auth import AuthContext
from app.schemas import CaptureCreate, CaptureRead, CaptureStatus
from app.services.image_store import save_image
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/captures", tags=["captures"])


@router.get("/reference-images")
async def get_reference_images(
    property_id: str,
    room: str,
    room_template_id: str = Query(default=""),
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    """Return reference thumbnails for ghost overlay.

    Priority:
    1. Owner reference images for the room template (all session types)
    2. Most recent move-in captures (move-out fallback)
    """
    # Try owner reference images first
    if room_template_id:
        owner_refs = await crud.list_reference_images(db, room_template_id)
        if owner_refs:
            return [
                {
                    "orientation_hint": img.position_hint,
                    "thumbnail_url": "/" + img.thumbnail_path,
                    "source": "owner",
                }
                for img in owner_refs
                if img.thumbnail_path
            ]

    # Fallback: move-in capture images
    images = await crud.get_movein_reference_images(db, property_id, room)
    return [
        {
            "orientation_hint": img.orientation_hint,
            "thumbnail_url": "/" + img.thumbnail_path,
            "source": "move_in",
        }
        for img in images
        if img.thumbnail_path
    ]


@router.post("", response_model=CaptureRead, status_code=201)
async def create_capture(
    body: CaptureCreate,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    sess = await crud.get_session(db, body.session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    cap = await crud.create_capture(db, body.session_id, body.room, body.device_meta)
    return cap


@router.post("/{capture_id}/images", status_code=201)
async def upload_image(
    capture_id: str,
    file: UploadFile = File(...),
    orientation_hint: str = Form(""),
    token: str = Form(""),
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")

    data = await file.read()
    seq = await crud.count_images_for_capture(db, capture_id) + 1
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[1].lower()

    orig_path, thumb_path = await save_image(data, capture_id, seq, ext, company_id=auth.company_id)
    img = await crud.create_capture_image(
        db, capture_id, seq, orig_path, thumb_path, orientation_hint
    )

    await ws_manager.broadcast(cap.session_id, {
        "event": "image_uploaded",
        "capture_id": capture_id,
        "image_id": img.id,
        "seq": seq,
        "thumbnail_path": thumb_path,
    })

    return {"id": img.id, "seq": seq, "file_path": orig_path, "thumbnail_path": thumb_path}


@router.delete("/{capture_id}/images/{image_id}", status_code=200)
async def delete_image(
    capture_id: str,
    image_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    """Delete a rejected or unwanted image from a capture."""
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")
    img = await crud.get_capture_image(db, image_id)
    if not img or img.capture_id != capture_id:
        raise HTTPException(404, "Image not found in this capture")

    from pathlib import Path
    for p in (img.file_path, img.thumbnail_path):
        if p:
            Path(p).unlink(missing_ok=True)

    await crud.delete_capture_image(db, img)

    await ws_manager.broadcast(cap.session_id, {
        "event": "image_deleted",
        "capture_id": capture_id,
        "image_id": image_id,
    })

    return {"deleted": image_id}


@router.post("/{capture_id}/submit")
async def submit_capture(
    capture_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    """Trigger quality gate + coverage review for this capture."""
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")
    if not cap.images:
        raise HTTPException(400, "No images uploaded")

    await crud.update_capture(db, cap, status="processing")

    # Launch agent pipeline in background with company_id for DB routing
    asyncio.create_task(_run_agents(capture_id, cap.session_id, auth.company_id))

    return {"status": "processing", "capture_id": capture_id}


async def _run_agents(capture_id: str, session_id: str, company_id: str):
    """Background task: run quality gate and coverage agents."""
    try:
        from app.agents.orchestrator import run_capture_pipeline
        factory = tenant_pool.session_factory(company_id)
        async with factory() as db:
            await run_capture_pipeline(capture_id, session_id, db, company_id=company_id)
    except Exception as e:
        await ws_manager.broadcast(session_id, {
            "event": "error",
            "capture_id": capture_id,
            "data": {"message": str(e)},
        })


@router.get("/{capture_id}/status", response_model=CaptureStatus)
async def get_capture_status(
    capture_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")
    return CaptureStatus(
        id=cap.id,
        status=cap.status,
        metrics_json=cap.metrics_json,
        coverage_json=cap.coverage_json,
        image_count=len(cap.images),
    )


@router.get("/{capture_id}/guidance")
async def get_capture_guidance(
    capture_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    """Return coverage agent's guidance for additional shots."""
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")
    coverage = cap.coverage_json or {}
    return {
        "capture_id": capture_id,
        "coverage_pct": coverage.get("coverage_pct", 0),
        "missing_areas": coverage.get("missing_areas", []),
        "instructions": coverage.get("instructions", []),
    }
