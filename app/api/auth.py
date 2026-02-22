"""Auth API: login, logout, MFA, password reset."""

from __future__ import annotations

import hashlib
import io
import secrets
from datetime import datetime, timezone, timedelta

import qrcode
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.auth_engine import get_auth_db
from app.dependencies import require_auth
from app.models.auth_models import User, PasswordReset
from app.services.auth import (
    AuthContext, verify_password, hash_password, SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_DAYS,
    create_session, remove_session, remove_all_user_sessions,
    generate_mfa_secret, get_mfa_provisioning_uri, verify_mfa_code,
    _hash_token,
)
from app.services.encryption import encrypt_value, decrypt_value
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class MFAVerifyRequest(BaseModel):
    email: str
    code: str
    # Temporary token issued after password verified but MFA pending
    mfa_token: str


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAEnableRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str
    code: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordForgotRequest(BaseModel):
    email: str


class PasswordResetRequest(BaseModel):
    token: str
    new_password: str


# ── Login / Logout ────────────────────────────────────────

@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_auth_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()

    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    # If MFA enabled, issue a short-lived MFA token instead of a full session
    if user.mfa_enabled:
        mfa_token = secrets.token_urlsafe(32)
        # Store temporarily — hash it so DB leak doesn't help
        user.last_login_at = None  # Will set after MFA
        # Use a password_resets row as a temp MFA challenge (expires in 5 min)
        challenge = PasswordReset(
            user_id=user.id,
            token_hash=_hash_token(mfa_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(challenge)
        await db.commit()
        return JSONResponse(content={"mfa_required": True, "mfa_token": mfa_token, "email": user.email})

    # No MFA — create full session
    ip = request.client.host if request.client else ""
    token = await create_session(user, db, ip_address=ip)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    response = JSONResponse(content={"ok": True, "user_id": user.id, "role": user.role})
    response.set_cookie(
        SESSION_COOKIE_NAME, token,
        httponly=True, samesite="lax",
        max_age=86400 * SESSION_MAX_AGE_DAYS,
    )
    return response


@router.post("/mfa/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_auth_db),
):
    """Complete login after MFA code verification."""
    # Find the MFA challenge token
    token_hash = _hash_token(body.mfa_token)
    result = await db.execute(
        select(PasswordReset).where(
            PasswordReset.token_hash == token_hash,
            PasswordReset.expires_at > datetime.now(timezone.utc),
        )
    )
    challenge = result.scalars().first()
    if not challenge:
        return JSONResponse(status_code=401, content={"detail": "MFA session expired"})

    user = await db.get(User, challenge.user_id)
    if not user or not user.is_active or user.email != body.email:
        return JSONResponse(status_code=401, content={"detail": "Invalid MFA session"})

    # Decrypt MFA secret and verify code
    try:
        mfa_secret = decrypt_value(user.mfa_secret)
    except Exception:
        mfa_secret = user.mfa_secret  # Fallback for unencrypted dev mode

    if not verify_mfa_code(mfa_secret, body.code):
        return JSONResponse(status_code=401, content={"detail": "Invalid MFA code"})

    # Clean up challenge
    await db.delete(challenge)

    # Create full session
    ip = request.client.host if request.client else ""
    token = await create_session(user, db, ip_address=ip)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    response = JSONResponse(content={"ok": True, "user_id": user.id, "role": user.role})
    response.set_cookie(
        SESSION_COOKIE_NAME, token,
        httponly=True, samesite="lax",
        max_age=86400 * SESSION_MAX_AGE_DAYS,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await remove_session(token, db)
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/me")
async def get_me(auth: AuthContext = Depends(require_auth)):
    return {
        "user_id": auth.user_id,
        "company_id": auth.company_id,
        "email": auth.email,
        "display_name": auth.display_name,
        "role": auth.role,
    }


# ── MFA Setup ─────────────────────────────────────────────

@router.post("/mfa/setup")
async def mfa_setup(
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    """Generate a new MFA secret + QR provisioning URI (doesn't enable yet)."""
    secret = generate_mfa_secret()
    uri = get_mfa_provisioning_uri(secret, auth.email)
    return {"secret": secret, "provisioning_uri": uri}


@router.get("/mfa/qr")
async def mfa_qr(
    secret: str,
    auth: AuthContext = Depends(require_auth),
):
    """Return a QR code PNG for the given TOTP secret."""
    uri = get_mfa_provisioning_uri(secret, auth.email)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.post("/mfa/enable")
async def mfa_enable(
    body: MFAEnableRequest,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    """Enable MFA after verifying a TOTP code. Secret must be passed in query or was recently set up."""
    # The secret should be stored temporarily by the frontend from /mfa/setup
    # We need the secret from the request — let's accept it
    return JSONResponse(status_code=400, content={"detail": "Use /mfa/enable-with-secret instead"})


@router.post("/mfa/enable-with-secret")
async def mfa_enable_with_secret(
    body: dict,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    """Enable MFA: verify code against provided secret, then store encrypted."""
    secret = body.get("secret", "")
    code = body.get("code", "")

    if not secret or not code:
        return JSONResponse(status_code=400, content={"detail": "secret and code required"})

    if not verify_mfa_code(secret, code):
        return JSONResponse(status_code=400, content={"detail": "Invalid code — check your authenticator app"})

    user = await db.get(User, auth.user_id)
    if not user:
        raise Exception("User not found")

    try:
        user.mfa_secret = encrypt_value(secret)
    except RuntimeError:
        user.mfa_secret = secret  # Dev mode fallback

    user.mfa_enabled = True
    await db.commit()

    return {"ok": True, "mfa_enabled": True}


@router.post("/mfa/disable")
async def mfa_disable(
    body: MFADisableRequest,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    """Disable MFA (requires password + current TOTP code)."""
    user = await db.get(User, auth.user_id)
    if not user:
        raise Exception("User not found")

    if not verify_password(body.password, user.password_hash):
        return JSONResponse(status_code=401, content={"detail": "Invalid password"})

    try:
        mfa_secret = decrypt_value(user.mfa_secret)
    except Exception:
        mfa_secret = user.mfa_secret

    if not verify_mfa_code(mfa_secret, body.code):
        return JSONResponse(status_code=401, content={"detail": "Invalid MFA code"})

    user.mfa_secret = ""
    user.mfa_enabled = False
    await db.commit()

    return {"ok": True, "mfa_enabled": False}


# ── Password Change ───────────────────────────────────────

@router.post("/password/change")
async def password_change(
    body: PasswordChangeRequest,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    """Change password for the currently logged-in user."""
    if len(body.new_password) < 8:
        return JSONResponse(status_code=400, content={"detail": "New password must be at least 8 characters"})

    user = await db.get(User, auth.user_id)
    if not user:
        return JSONResponse(status_code=400, content={"detail": "User not found"})

    if not verify_password(body.current_password, user.password_hash):
        return JSONResponse(status_code=401, content={"detail": "Current password is incorrect"})

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    return {"ok": True, "message": "Password updated"}


# ── Password Reset ────────────────────────────────────────

@router.post("/password/forgot")
async def password_forgot(
    body: PasswordForgotRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Send a password reset email (always returns 200 to prevent enumeration)."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()

    if user and user.is_active:
        token = secrets.token_urlsafe(48)
        reset = PasswordReset(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset)
        await db.commit()
        send_password_reset_email(user.email, token)

    return {"ok": True, "message": "If an account exists, a reset link has been sent."}


@router.post("/password/reset")
async def password_reset(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Reset password using a valid token."""
    if len(body.new_password) < 8:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 8 characters"})

    token_hash = _hash_token(body.token)
    result = await db.execute(
        select(PasswordReset).where(
            PasswordReset.token_hash == token_hash,
            PasswordReset.expires_at > datetime.now(timezone.utc),
        )
    )
    reset = result.scalars().first()
    if not reset:
        return JSONResponse(status_code=400, content={"detail": "Invalid or expired reset token"})

    user = await db.get(User, reset.user_id)
    if not user:
        return JSONResponse(status_code=400, content={"detail": "User not found"})

    user.password_hash = hash_password(body.new_password)
    await db.delete(reset)

    # Invalidate all existing sessions
    await remove_all_user_sessions(user.id, db)

    await db.commit()
    return {"ok": True, "message": "Password updated. Please log in."}
