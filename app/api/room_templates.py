"""Room template CRUD API endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, get_company_db
from app.services.auth import AuthContext
from app.services.image_store import save_image
from app.schemas.room_template import RoomTemplateCreate, RoomTemplateRead, RoomTemplateUpdate

router = APIRouter(prefix="/api/owner", tags=["room-templates"])


@router.post("/properties/{property_id}/rooms", response_model=RoomTemplateRead)
async def create_room(
    property_id: str,
    body: RoomTemplateCreate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    positions = [p.model_dump() for p in body.positions]
    rt = await crud.create_room_template(db, property_id, body.name, body.display_order, positions)
    return RoomTemplateRead.model_validate(rt)


@router.get("/properties/{property_id}/rooms")
async def list_rooms(
    property_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    templates = await crud.list_room_templates_for_property(db, property_id)
    return [RoomTemplateRead.model_validate(rt) for rt in templates]


@router.put("/rooms/{room_id}", response_model=RoomTemplateRead)
async def update_room(
    room_id: str,
    body: RoomTemplateUpdate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.display_order is not None:
        updates["display_order"] = body.display_order
    if body.positions is not None:
        updates["positions"] = [p.model_dump() for p in body.positions]

    if updates:
        rt = await crud.update_room_template(db, rt, **updates)
    return RoomTemplateRead.model_validate(rt)


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    # Clean up reference image files from disk before cascade delete
    ref_images = await crud.list_reference_images(db, room_id)
    for img in ref_images:
        for p in (img.file_path, img.thumbnail_path):
            if p:
                Path(p).unlink(missing_ok=True)

    await crud.delete_room_template(db, rt)
    return {"ok": True}


# ── Reference Images ─────────────────────────────────────

@router.post("/rooms/{room_id}/reference-images", status_code=201)
async def upload_reference_image(
    room_id: str,
    file: UploadFile = File(...),
    position_hint: str = Form(...),
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Upload a reference photo for a room template position.

    Replaces any existing image at the same position.
    """
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    # Replace existing image at this position
    existing = await crud.get_reference_image_by_position(db, room_id, position_hint)
    if existing:
        for p in (existing.file_path, existing.thumbnail_path):
            if p:
                Path(p).unlink(missing_ok=True)
        await crud.delete_reference_image(db, existing)

    data = await file.read()
    seq = await crud.count_reference_images(db, room_id) + 1
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[1].lower()

    # Store under ref_{room_template_id} directory
    storage_key = f"ref_{room_id}"
    orig_path, thumb_path = await save_image(
        data, storage_key, seq, ext, company_id=auth.company_id
    )

    img = await crud.create_reference_image(
        db, room_id, position_hint, seq, orig_path, thumb_path
    )
    return {
        "id": img.id,
        "position_hint": img.position_hint,
        "seq": img.seq,
        "file_path": orig_path,
        "thumbnail_path": thumb_path,
    }


@router.get("/rooms/{room_id}/reference-images")
async def list_reference_images(
    room_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """List all reference images for a room template."""
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    images = await crud.list_reference_images(db, room_id)
    return [
        {
            "id": img.id,
            "position_hint": img.position_hint,
            "seq": img.seq,
            "thumbnail_url": "/" + img.thumbnail_path if img.thumbnail_path else None,
            "created_at": img.created_at.isoformat(),
        }
        for img in images
    ]


@router.delete("/reference-images/{image_id}")
async def delete_reference_image(
    image_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Delete a reference image and clean up files."""
    img = await crud.get_reference_image_by_id(db, image_id)
    if not img:
        raise HTTPException(404, "Reference image not found")

    for p in (img.file_path, img.thumbnail_path):
        if p:
            Path(p).unlink(missing_ok=True)

    await crud.delete_reference_image(db, img)
    return {"deleted": image_id}
