from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud
from app.schemas import CandidateRead, CandidateResponse
from app.services.image_store import save_image

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.post("/{candidate_id}/response", response_model=CandidateRead)
async def respond_to_candidate(
    candidate_id: str, body: CandidateResponse, db: AsyncSession = Depends(get_db)
):
    cand = await crud.get_candidate(db, candidate_id)
    if not cand:
        raise HTTPException(404, "Candidate not found")
    if body.response not in ("confirm", "disagree"):
        raise HTTPException(400, "response must be 'confirm' or 'disagree'")
    cand = await crud.update_candidate(
        db, cand,
        tenant_response=body.response,
        tenant_comment=body.comment,
        followup_status="responded",
    )
    return cand


@router.post("/{candidate_id}/closeup", response_model=CandidateRead)
async def upload_closeup(
    candidate_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    cand = await crud.get_candidate(db, candidate_id)
    if not cand:
        raise HTTPException(404, "Candidate not found")
    data = await file.read()
    # Store close-up alongside comparison crops
    comp = await crud.get_comparison(db, cand.comparison_id)
    crop_dir = f"data/images/comparisons/{comp.id}/closeups"
    from pathlib import Path
    Path(crop_dir).mkdir(parents=True, exist_ok=True)
    crop_path = f"{crop_dir}/{candidate_id}.jpg"
    Path(crop_path).write_bytes(data)
    cand = await crud.update_candidate(
        db, cand, crop_path=crop_path, followup_status="closeup_uploaded"
    )
    return cand
