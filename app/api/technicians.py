"""Technician management API — owner access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, get_company_db

router = APIRouter(prefix="/api/owner/technicians", tags=["technicians"])


@router.get("")
async def list_technicians(
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    techs = await crud.list_technicians(db, active_only=True)
    return [
        {
            "id": t.id,
            "name": t.name,
            "email": t.email,
            "phone": t.phone,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat(),
        }
        for t in techs
    ]


@router.post("", status_code=201)
async def create_technician(
    body: dict,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    if not name or not email:
        raise HTTPException(400, "Name and email are required")

    tech = await crud.create_technician(
        db, name=name, email=email, phone=body.get("phone", ""),
    )
    return {
        "id": tech.id,
        "name": tech.name,
        "email": tech.email,
        "phone": tech.phone,
        "is_active": tech.is_active,
    }


@router.put("/{tech_id}")
async def update_technician(
    tech_id: str,
    body: dict,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    tech = await crud.get_technician(db, tech_id)
    if not tech:
        raise HTTPException(404, "Technician not found")

    updates = {}
    for field in ("name", "email", "phone"):
        if field in body:
            updates[field] = body[field]

    if updates:
        tech = await crud.update_technician(db, tech, **updates)

    return {
        "id": tech.id,
        "name": tech.name,
        "email": tech.email,
        "phone": tech.phone,
        "is_active": tech.is_active,
    }


@router.delete("/{tech_id}")
async def delete_technician(
    tech_id: str,
    auth=Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    tech = await crud.get_technician(db, tech_id)
    if not tech:
        raise HTTPException(404, "Technician not found")

    tech = await crud.update_technician(db, tech, is_active=False)
    return {"ok": True, "id": tech.id}
