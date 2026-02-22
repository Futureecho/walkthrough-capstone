"""Admin API: user management, invites, company settings."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.auth_engine import get_auth_db
from app.dependencies import require_role
from app.models.auth_models import User, Company, Invite
from app.services.auth import AuthContext, hash_password, _hash_token
from app.services.email import send_invite_email

router = APIRouter(prefix="/api/admin", tags=["admin"])

_admin_dep = require_role("admin")


# ── Schemas ───────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: str
    role: str = "inspector"


class UserRoleUpdate(BaseModel):
    role: str


class CompanyUpdate(BaseModel):
    name: str | None = None


# ── Invites ───────────────────────────────────────────────

@router.post("/invite")
async def send_invite(
    body: InviteRequest,
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    if body.role not in ("admin", "inspector", "viewer"):
        return JSONResponse(status_code=400, content={"detail": "Invalid role"})

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalars().first():
        return JSONResponse(status_code=409, content={"detail": "User with this email already exists"})

    # Check for existing pending invite
    result = await db.execute(
        select(Invite).where(
            Invite.email == body.email,
            Invite.company_id == auth.company_id,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    if result.scalars().first():
        return JSONResponse(status_code=409, content={"detail": "Pending invite already exists for this email"})

    token = secrets.token_urlsafe(48)
    invite = Invite(
        company_id=auth.company_id,
        email=body.email,
        role=body.role,
        token_hash=_hash_token(token),
        invited_by=auth.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()

    # Get company name for email
    company = await db.get(Company, auth.company_id)
    company_name = company.name if company else "your company"

    send_invite_email(body.email, token, company_name, auth.display_name or auth.email)

    return {"ok": True, "email": body.email, "role": body.role}


# ── Users ─────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    result = await db.execute(
        select(User).where(User.company_id == auth.company_id).order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "mfa_enabled": u.mfa_enabled,
            "created_at": u.created_at.isoformat(),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    if body.role not in ("admin", "inspector", "viewer"):
        return JSONResponse(status_code=400, content={"detail": "Invalid role"})

    user = await db.get(User, user_id)
    if not user or user.company_id != auth.company_id:
        raise HTTPException(404, "User not found")

    # Prevent removing the last admin
    if user.role == "admin" and body.role != "admin":
        result = await db.execute(
            select(User).where(
                User.company_id == auth.company_id,
                User.role == "admin",
                User.is_active == True,
            )
        )
        admin_count = len(result.scalars().all())
        if admin_count <= 1:
            return JSONResponse(status_code=400, content={"detail": "Cannot remove the last admin"})

    user.role = body.role
    await db.commit()
    return {"ok": True, "user_id": user.id, "role": user.role}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    if user_id == auth.user_id:
        return JSONResponse(status_code=400, content={"detail": "Cannot deactivate yourself"})

    user = await db.get(User, user_id)
    if not user or user.company_id != auth.company_id:
        raise HTTPException(404, "User not found")

    user.is_active = False
    await db.commit()
    return {"ok": True, "user_id": user.id}


# ── Company ───────────────────────────────────────────────

@router.get("/company")
async def get_company(
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    company = await db.get(Company, auth.company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "is_active": company.is_active,
        "created_at": company.created_at.isoformat(),
    }


@router.put("/company")
async def update_company(
    body: CompanyUpdate,
    auth: AuthContext = Depends(_admin_dep),
    db: AsyncSession = Depends(get_auth_db),
):
    company = await db.get(Company, auth.company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    if body.name is not None:
        company.name = body.name
    await db.commit()
    return {"ok": True, "name": company.name}
