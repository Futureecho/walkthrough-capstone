"""Room template CRUD API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud
from app.services.auth import get_current_owner
from app.schemas.room_template import RoomTemplateCreate, RoomTemplateRead, RoomTemplateUpdate

router = APIRouter(prefix="/api/owner", tags=["room-templates"])


@router.post("/properties/{property_id}/rooms", response_model=RoomTemplateRead)
async def create_room(
    property_id: str,
    body: RoomTemplateCreate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Property not found")

    positions = [p.model_dump() for p in body.positions]
    rt = await crud.create_room_template(db, property_id, body.name, body.display_order, positions)
    return RoomTemplateRead.model_validate(rt)


@router.get("/properties/{property_id}/rooms")
async def list_rooms(
    property_id: str,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Property not found")

    templates = await crud.list_room_templates_for_property(db, property_id)
    return [RoomTemplateRead.model_validate(rt) for rt in templates]


@router.put("/rooms/{room_id}", response_model=RoomTemplateRead)
async def update_room(
    room_id: str,
    body: RoomTemplateUpdate,
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    prop = await crud.get_property(db, rt.property_id)
    if not prop or prop.owner_id != owner_id:
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
    owner_id: str = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    rt = await crud.get_room_template(db, room_id)
    if not rt:
        raise HTTPException(404, "Room template not found")

    prop = await crud.get_property(db, rt.property_id)
    if not prop or prop.owner_id != owner_id:
        raise HTTPException(404, "Room template not found")

    await crud.delete_room_template(db, rt)
    return {"ok": True}
