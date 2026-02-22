from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth, get_company_db
from app.services.auth import AuthContext

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{property_id}", response_class=HTMLResponse)
async def get_report(
    property_id: str,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_company_db),
):
    prop = await crud.get_property(db, property_id)
    if not prop:
        raise HTTPException(404, "Property not found")

    from app.services.report_generator import generate_report
    html = await generate_report(db, prop)
    return HTMLResponse(content=html)
