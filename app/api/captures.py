from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db, async_session_factory
from app.db import crud
from app.schemas import CaptureCreate, CaptureRead, CaptureStatus
from app.services.image_store import save_image
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/captures", tags=["captures"])


@router.post("", response_model=CaptureRead, status_code=201)
async def create_capture(body: CaptureCreate, db: AsyncSession = Depends(get_db)):
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
    db: AsyncSession = Depends(get_db),
):
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")

    data = await file.read()
    seq = await crud.count_images_for_capture(db, capture_id) + 1
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[1].lower()

    orig_path, thumb_path = await save_image(data, capture_id, seq, ext)
    img = await crud.create_capture_image(
        db, capture_id, seq, orig_path, thumb_path, orientation_hint
    )

    # Notify connected clients
    await ws_manager.broadcast(cap.session_id, {
        "event": "image_uploaded",
        "capture_id": capture_id,
        "image_id": img.id,
        "seq": seq,
        "thumbnail_path": thumb_path,
    })

    return {"id": img.id, "seq": seq, "file_path": orig_path, "thumbnail_path": thumb_path}


@router.post("/{capture_id}/submit")
async def submit_capture(capture_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger quality gate + coverage review for this capture."""
    cap = await crud.get_capture(db, capture_id)
    if not cap:
        raise HTTPException(404, "Capture not found")
    if not cap.images:
        raise HTTPException(400, "No images uploaded")

    await crud.update_capture(db, cap, status="processing")

    # Launch agent pipeline in background
    asyncio.create_task(_run_agents(capture_id, cap.session_id))

    return {"status": "processing", "capture_id": capture_id}


async def _run_agents(capture_id: str, session_id: str):
    """Background task: run quality gate and coverage agents."""
    try:
        from app.agents.orchestrator import run_capture_pipeline
        async with async_session_factory() as db:
            await run_capture_pipeline(capture_id, session_id, db)
    except Exception as e:
        await ws_manager.broadcast(session_id, {
            "event": "error",
            "capture_id": capture_id,
            "data": {"message": str(e)},
        })


@router.get("/{capture_id}/status", response_model=CaptureStatus)
async def get_capture_status(capture_id: str, db: AsyncSession = Depends(get_db)):
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
async def get_capture_guidance(capture_id: str, db: AsyncSession = Depends(get_db)):
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
