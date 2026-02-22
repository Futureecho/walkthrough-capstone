from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, get_company_db
from app.services.auth import AuthContext
from app.schemas import PropertyCreate, PropertyRead

router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.post("", response_model=PropertyRead, status_code=201)
async def create_property(
    body: PropertyCreate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.create_property(db, body.label, body.rooms)
    return prop


@router.get("", response_model=list[PropertyRead])
async def list_properties(
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    return await crud.list_properties(db)


@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(
    property_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    return prop
