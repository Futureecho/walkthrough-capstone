"""Invite acceptance API: validate invite, create account, join via link."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.auth_engine import get_auth_db
from app.models.auth_models import Invite, User, Company, Referral
from app.services.auth import hash_password, _hash_token

router = APIRouter(prefix="/api", tags=["invite"])


class InviteAcceptRequest(BaseModel):
    display_name: str
    password: str


class JoinRequest(BaseModel):
    display_name: str
    email: str
    password: str
    company_name: str = ""  # only used for referral joins


@router.get("/invite/{token}")
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

    company = await db.get(Company, invite.company_id)

    return {
        "email": invite.email,
        "role": invite.role,
        "company_name": company.name if company else "",
    }


@router.post("/invite/{token}/accept")
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


# ── Join (shareable link) endpoints ──────────────────────

async def _find_invite_or_referral(token_hash: str, db: AsyncSession):
    """Look up token in Invite then Referral tables. Returns (type, record)."""
    result = await db.execute(
        select(Invite).where(
            Invite.token_hash == token_hash,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalars().first()
    if invite:
        return "invite", invite

    result = await db.execute(
        select(Referral).where(
            Referral.token_hash == token_hash,
            Referral.accepted_at.is_(None),
            Referral.expires_at > datetime.now(timezone.utc),
        )
    )
    referral = result.scalars().first()
    if referral:
        return "referral", referral

    return None, None


@router.get("/join/{token}")
async def validate_join_token(
    token: str,
    db: AsyncSession = Depends(get_auth_db),
):
    """Validate a join token (invite link or referral link)."""
    token_hash = _hash_token(token)
    kind, record = await _find_invite_or_referral(token_hash, db)

    if not record:
        raise HTTPException(404, "Invalid or expired link")

    if kind == "invite":
        company = await db.get(Company, record.company_id)
        return {
            "type": "invite",
            "role": record.role,
            "company_name": company.name if company else "",
        }
    else:
        company = await db.get(Company, record.referred_by_company_id)
        return {
            "type": "referral",
            "role": "admin",
            "company_name": "",
            "referred_by": company.name if company else "",
        }


@router.post("/join/{token}")
async def accept_join_token(
    token: str,
    body: JoinRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Accept a join link: create account (team invite or referral)."""
    if len(body.password) < 8:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 8 characters"})
    if not body.email or not body.email.strip():
        return JSONResponse(status_code=400, content={"detail": "Email is required"})
    if not body.display_name or not body.display_name.strip():
        return JSONResponse(status_code=400, content={"detail": "Display name is required"})

    token_hash = _hash_token(token)
    kind, record = await _find_invite_or_referral(token_hash, db)

    if not record:
        raise HTTPException(404, "Invalid or expired link")

    # Check email not already taken
    result = await db.execute(select(User).where(User.email == body.email.strip()))
    if result.scalars().first():
        return JSONResponse(status_code=409, content={"detail": "An account with this email already exists"})

    if kind == "invite":
        user = User(
            company_id=record.company_id,
            email=body.email.strip(),
            display_name=body.display_name.strip(),
            password_hash=hash_password(body.password),
            role=record.role,
        )
        db.add(user)
        record.accepted_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True, "type": "invite", "user_id": user.id, "email": user.email}

    else:  # referral
        if not body.company_name or not body.company_name.strip():
            return JSONResponse(status_code=400, content={"detail": "Company name is required for referral signups"})

        from app.services.company_bootstrap import create_company
        company, admin_user = await create_company(
            name=body.company_name.strip(),
            admin_email=body.email.strip(),
            admin_password=body.password,
            auth_db=db,
            admin_display_name=body.display_name.strip(),
        )
        record.accepted_at = datetime.now(timezone.utc)
        record.new_company_id = company.id
        await db.commit()
        return {"ok": True, "type": "referral", "user_id": admin_user.id, "email": admin_user.email, "company_name": company.name}
