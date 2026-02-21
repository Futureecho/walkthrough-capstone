from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{property_id}", response_class=HTMLResponse)
async def get_report(property_id: str, db: AsyncSession = Depends(get_db)):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    from app.services.report_generator import generate_report
    html = await generate_report(db, prop)
    return HTMLResponse(content=html)
