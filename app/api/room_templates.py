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
    rt = await crud.create_room_template(
        db, property_id, body.name, body.display_order, positions,
        capture_mode=body.capture_mode,
    )
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
    if body.capture_mode is not None:
        updates["capture_mode"] = body.capture_mode

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


# ── Reference Image Sets ─────────────────────────────────

@router.post("/rooms/{room_id}/reference-sets", status_code=201)
async def create_reference_set(
    room_id: str,
    body: dict,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Create a new reference image set for a room."""
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    ref_set = await crud.create_reference_image_set(
        db, room_id,
        label=body.get("label", ""),
        capture_mode=body.get("capture_mode", rt.capture_mode),
    )
    return {
        "id": ref_set.id,
        "room_template_id": ref_set.room_template_id,
        "label": ref_set.label,
        "capture_mode": ref_set.capture_mode,
        "image_count": ref_set.image_count,
        "created_at": ref_set.created_at.isoformat(),
    }


@router.get("/rooms/{room_id}/reference-sets")
async def list_reference_sets(
    room_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """List all reference image sets for a room, newest first."""
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    sets = await crud.list_reference_image_sets(db, room_id)
    return [
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
        for s in sets
    ]


@router.delete("/reference-sets/{set_id}")
async def delete_reference_set(
    set_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Delete a reference image set and clean up files."""
    ref_set = await crud.get_reference_image_set(db, set_id)
    if not ref_set:
        raise HTTPException(404, "Reference set not found")

    # Clean up files
    for img in (ref_set.images or []):
        for p in (img.file_path, img.thumbnail_path):
            if p:
                Path(p).unlink(missing_ok=True)

    # If this was the active set, clear the active pointer
    rt = await crud.get_room_template(db, ref_set.room_template_id)
    if rt and rt.active_ref_set_id == set_id:
        await crud.update_room_template(db, rt, active_ref_set_id=None)

    await crud.delete_reference_image_set(db, ref_set)
    return {"deleted": set_id}


@router.post("/reference-sets/{set_id}/activate")
async def activate_reference_set(
    set_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Set this reference set as the active baseline for its room."""
    ref_set = await crud.get_reference_image_set(db, set_id)
    if not ref_set:
        raise HTTPException(404, "Reference set not found")

    rt = await crud.get_room_template(db, ref_set.room_template_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    await crud.update_room_template(db, rt, active_ref_set_id=set_id)
    return {"ok": True, "active_ref_set_id": set_id}


# ── Reference Images ─────────────────────────────────────

@router.post("/rooms/{room_id}/reference-images", status_code=201)
async def upload_reference_image(
    room_id: str,
    file: UploadFile = File(...),
    position_hint: str = Form(...),
    set_id: str = Form(""),
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    """Upload a reference photo for a room template position.

    If set_id is provided, the image is added to that set.
    Otherwise, replaces any existing image at the same position (legacy behavior).
    """
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    if not set_id:
        # Legacy behavior: replace existing at this position
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

    storage_key = f"ref_{room_id}"
    orig_path, thumb_path = await save_image(
        data, storage_key, seq, ext, company_id=auth.company_id
    )

    img = await crud.create_reference_image(
        db, room_id, position_hint, seq, orig_path, thumb_path
    )

    # Assign to set if provided
    if set_id:
        img.set_id = set_id
        await db.commit()
        await db.refresh(img)
        # Update set image_count
        ref_set = await crud.get_reference_image_set(db, set_id)
        if ref_set:
            ref_set.image_count = len(ref_set.images)
            await db.commit()

    return {
        "id": img.id,
        "set_id": img.set_id,
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
            "set_id": img.set_id,
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

    set_id = img.set_id

    for p in (img.file_path, img.thumbnail_path):
        if p:
            Path(p).unlink(missing_ok=True)

    await crud.delete_reference_image(db, img)

    # Update set image_count if it belonged to a set
    if set_id:
        ref_set = await crud.get_reference_image_set(db, set_id)
        if ref_set:
            ref_set.image_count = len(ref_set.images)
            await db.commit()

    return {"deleted": image_id}
