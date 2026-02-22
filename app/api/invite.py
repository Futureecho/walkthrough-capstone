"""Invite acceptance API: validate invite, create account."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.auth_engine import get_auth_db
from app.models.auth_models import Invite, User
from app.services.auth import hash_password, _hash_token

router = APIRouter(prefix="/api/invite", tags=["invite"])


class InviteAcceptRequest(BaseModel):
    display_name: str
    password: str


@router.get("/{token}")
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_auth_db),
):
    """Check if an invite token is valid."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(Invite).where(
            Invite.token_hash == token_hash,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(404, "Invalid or expired invite")

    from app.models.auth_models import Company
    company = await db.get(Company, invite.company_id)

    return {
        "email": invite.email,
        "role": invite.role,
        "company_name": company.name if company else "",
    }


@router.post("/{token}/accept")
async def accept_invite(
    token: str,
    body: InviteAcceptRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Accept an invite: create user account."""
    if len(body.password) < 8:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 8 characters"})

    token_hash = _hash_token(token)
    result = await db.execute(
        select(Invite).where(
            Invite.token_hash == token_hash,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(404, "Invalid or expired invite")

    # Check email not already taken
    result = await db.execute(select(User).where(User.email == invite.email))
    if result.scalars().first():
        return JSONResponse(status_code=409, content={"detail": "An account with this email already exists"})

    user = User(
        company_id=invite.company_id,
        email=invite.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=invite.role,
    )
    db.add(user)

    invite.accepted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True, "user_id": user.id, "email": user.email}
