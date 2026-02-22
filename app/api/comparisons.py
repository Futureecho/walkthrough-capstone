from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.dependencies import require_auth_or_tenant, get_company_db_flexible
from app.services.auth import AuthContext
from app.schemas import ComparisonRead

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


@router.get("/{comparison_id}", response_model=ComparisonRead)
async def get_comparison(
    comparison_id: str,
    auth: AuthContext = Depends(require_auth_or_tenant),
    db: AsyncSession = Depends(get_company_db_flexible),
):
    comp = await crud.get_comparison(db, comparison_id)
    if not comp:
        raise HTTPException(404, "Comparison not found")
    return comp
