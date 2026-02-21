"""Owner login/logout/setup API endpoints."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db import crud
from app.schemas.owner import OwnerLogin
from app.services.auth import (
    hash_password, verify_password, create_session_token,
    remove_session_token, get_current_owner, SESSION_COOKIE_NAME,
)

router = APIRouter(prefix="/api/owner", tags=["owner-auth"])


class OwnerSetup(BaseModel):
    username: str
    password: str
    password_hint: str = ""


@router.get("/status")
async def owner_status(db: AsyncSession = Depends(get_db)):
    """Check if an owner account exists (for first-run setup detection)."""
    from app.models import Owner
    from sqlalchemy import select, func
    result = await db.execute(select(func.count()).select_from(Owner))
    count = result.scalar() or 0
    return {"setup_required": count == 0}


@router.post("/setup")
async def owner_setup(body: OwnerSetup, db: AsyncSession = Depends(get_db)):
    """First-run setup: create the owner account."""
    from app.models import Owner
    from sqlalchemy import select, func
    result = await db.execute(select(func.count()).select_from(Owner))
    count = result.scalar() or 0
    if count > 0:
        return JSONResponse(status_code=409, content={"detail": "Owner already exists"})

    if len(body.password) < 6:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 6 characters"})

    pw_hash = hash_password(body.password)
    owner = await crud.create_owner(db, body.username, pw_hash)

    # Save password hint
    owner.password_hint = body.password_hint
    await db.commit()
    await db.refresh(owner)

    # Create default settings
    await crud.create_owner_settings(db, owner.id)

    # Auto-login after setup
    token = create_session_token(owner.id)
    response = JSONResponse(content={"ok": True, "owner_id": owner.id})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@router.post("/login")
async def owner_login(body: OwnerLogin, db: AsyncSession = Depends(get_db)):
    owner = await crud.get_owner_by_username(db, body.username)
    if not owner or not verify_password(body.password, owner.password_hash):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    token = create_session_token(owner.id)
    response = JSONResponse(content={"ok": True, "owner_id": owner.id})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@router.post("/logout")
async def owner_logout(request: Request, owner_id: str = Depends(get_current_owner)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        remove_session_token(token)
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/hint")
async def get_password_hint(username: str = "", db: AsyncSession = Depends(get_db)):
    """Return the password hint for an owner (if set)."""
    if not username:
        # If only one owner, return their hint
        from app.models import Owner
        from sqlalchemy import select
        result = await db.execute(select(Owner))
        owner = result.scalars().first()
    else:
        owner = await crud.get_owner_by_username(db, username)

    if not owner or not owner.password_hint:
        return {"hint": ""}
    return {"hint": owner.password_hint}
